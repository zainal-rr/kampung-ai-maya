from __future__ import annotations

import ctypes
import threading
from dataclasses import dataclass
from typing import Callable


CARBON = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Carbon.framework/Carbon")
CORE_FOUNDATION = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")


OPTION_KEY = 1 << 11
CONTROL_KEY = 1 << 12
SHIFT_KEY = 1 << 9
COMMAND_KEY = 1 << 8

KEY_CODES = {
    "space": 49,
    "esc": 53,
    "escape": 53,
}

MODIFIERS = {
    "alt": OPTION_KEY,
    "option": OPTION_KEY,
    "ctrl": CONTROL_KEY,
    "control": CONTROL_KEY,
    "shift": SHIFT_KEY,
    "cmd": COMMAND_KEY,
    "command": COMMAND_KEY,
}


def _four_char_code(value: str) -> int:
    result = 0
    for char in value.encode("macroman"):
        result = (result << 8) + char
    return result


K_EVENT_CLASS_KEYBOARD = _four_char_code("keyb")
K_EVENT_HOTKEY_PRESSED = 5
K_EVENT_PARAM_DIRECT_OBJECT = _four_char_code("----")
TYPE_EVENT_HOTKEY_ID = _four_char_code("hkid")
MAYA_SIGNATURE = _four_char_code("MAYA")
NO_ERR = 0


class EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


EventHandlerProcPtr = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


CARBON.GetApplicationEventTarget.restype = ctypes.c_void_p
CARBON.GetEventDispatcherTarget.restype = ctypes.c_void_p
CARBON.InstallEventHandler.argtypes = [
    ctypes.c_void_p,
    EventHandlerProcPtr,
    ctypes.c_uint32,
    ctypes.POINTER(EventTypeSpec),
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
]
CARBON.InstallEventHandler.restype = ctypes.c_int32
CARBON.RegisterEventHotKey.argtypes = [
    ctypes.c_uint32,
    ctypes.c_uint32,
    EventHotKeyID,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_void_p),
]
CARBON.RegisterEventHotKey.restype = ctypes.c_int32
CARBON.GetEventParameter.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
CARBON.GetEventParameter.restype = ctypes.c_int32
CARBON.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
CARBON.UnregisterEventHotKey.restype = ctypes.c_int32
CORE_FOUNDATION.CFRunLoopRun.argtypes = []
CORE_FOUNDATION.CFRunLoopRun.restype = None
CORE_FOUNDATION.CFRunLoopStop.argtypes = [ctypes.c_void_p]
CORE_FOUNDATION.CFRunLoopStop.restype = None
CORE_FOUNDATION.CFRunLoopGetCurrent.argtypes = []
CORE_FOUNDATION.CFRunLoopGetCurrent.restype = ctypes.c_void_p


@dataclass(frozen=True)
class ParsedHotkey:
    key_code: int
    modifiers: int


class CarbonHotKeyListener:
    def __init__(self, bindings: dict[str, Callable[[], None]]):
        self.bindings = bindings
        self.callbacks_by_id: dict[int, Callable[[], None]] = {}
        self.hotkey_refs: list[ctypes.c_void_p] = []
        self.handler_ref = ctypes.c_void_p()
        self.callback_ref = EventHandlerProcPtr(self._handle_event)
        self.thread: threading.Thread | None = None
        self.run_loop = None
        self.errors: list[str] = []

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="MayaCarbonHotKey", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        for ref in self.hotkey_refs:
            if ref:
                CARBON.UnregisterEventHotKey(ref)
        self.hotkey_refs.clear()
        # Do not call CFRunLoopStop from another Python/AppKit callback thread.
        # In the packaged app this can trip macOS pointer-authentication checks
        # during NSApplication termination. The listener thread is daemonized, so
        # unregistering hotkeys is enough for shutdown.

    def _run(self) -> None:
        try:
            self._run_inner()
        except Exception as exc:
            self.errors.append(f"Carbon hotkey thread failed: {exc}")
            print(f"maya-hotkey> carbon hotkey thread failed: {exc}", flush=True)

    def _run_inner(self) -> None:
        print("maya-hotkey> carbon thread starting", flush=True)
        self.run_loop = CORE_FOUNDATION.CFRunLoopGetCurrent()
        target = CARBON.GetEventDispatcherTarget()
        event_type = EventTypeSpec(K_EVENT_CLASS_KEYBOARD, K_EVENT_HOTKEY_PRESSED)
        status = CARBON.InstallEventHandler(
            target,
            self.callback_ref,
            1,
            ctypes.byref(event_type),
            None,
            ctypes.byref(self.handler_ref),
        )
        if status != NO_ERR:
            self.errors.append(f"InstallEventHandler failed: {status}")
            print(f"maya-hotkey> carbon install handler failed: {status}", flush=True)
            return
        for hotkey_id, (combo, callback) in enumerate(self.bindings.items(), start=1):
            parsed = parse_hotkey(combo)
            hotkey_ref = ctypes.c_void_p()
            carbon_id = EventHotKeyID(MAYA_SIGNATURE, hotkey_id)
            status = CARBON.RegisterEventHotKey(
                parsed.key_code,
                parsed.modifiers,
                carbon_id,
                target,
                0,
                ctypes.byref(hotkey_ref),
            )
            if status != NO_ERR:
                self.errors.append(f"RegisterEventHotKey failed for {combo}: {status}")
                print(f"maya-hotkey> carbon register failed for {combo}: {status}", flush=True)
                continue
            self.callbacks_by_id[hotkey_id] = callback
            self.hotkey_refs.append(hotkey_ref)
            print(f"maya-hotkey> carbon registered {combo}", flush=True)
        if not self.callbacks_by_id:
            return
        CORE_FOUNDATION.CFRunLoopRun()

    def _handle_event(self, next_handler, event, user_data) -> int:
        hotkey_id = EventHotKeyID()
        status = CARBON.GetEventParameter(
            event,
            K_EVENT_PARAM_DIRECT_OBJECT,
            TYPE_EVENT_HOTKEY_ID,
            None,
            ctypes.sizeof(hotkey_id),
            None,
            ctypes.byref(hotkey_id),
        )
        if status == NO_ERR:
            callback = self.callbacks_by_id.get(hotkey_id.id)
            if callback:
                callback()
        return NO_ERR


def parse_hotkey(combo: str) -> ParsedHotkey:
    clean = combo.replace("<", "").replace(">", "")
    parts = [part.strip().lower() for part in clean.split("+") if part.strip()]
    modifiers = 0
    key_code = None
    for part in parts:
        if part in MODIFIERS:
            modifiers |= MODIFIERS[part]
        elif part in KEY_CODES:
            key_code = KEY_CODES[part]
    if key_code is None:
        raise ValueError(f"Unsupported macOS hotkey: {combo}")
    return ParsedHotkey(key_code, modifiers)
