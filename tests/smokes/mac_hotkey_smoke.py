from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import mac_hotkey
from mac_hotkey import OPTION_KEY, CarbonHotKeyListener, parse_hotkey


def main() -> None:
    start = parse_hotkey("<alt>+<space>")
    stop = parse_hotkey("<alt>+<esc>")
    assert start.key_code == 49
    assert start.modifiers == OPTION_KEY
    assert stop.key_code == 53
    assert stop.modifiers == OPTION_KEY
    calls = []
    original_stop = mac_hotkey.CORE_FOUNDATION.CFRunLoopStop
    try:
        mac_hotkey.CORE_FOUNDATION.CFRunLoopStop = calls.append
        listener = CarbonHotKeyListener({})
        listener.run_loop = object()
        listener.stop()
        assert calls == []
    finally:
        mac_hotkey.CORE_FOUNDATION.CFRunLoopStop = original_stop
    print("mac_hotkey_smoke: ok")


if __name__ == "__main__":
    main()
