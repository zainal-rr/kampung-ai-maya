from __future__ import annotations

import sounddevice as sd

from maya_runtime_config import normalized_names, runtime_config


def local_wake_allowed(input_name: str = "", output_name: str = "") -> bool:
    names = _joined_names(input_name, output_name)
    if _matches(names, _blocked_names()):
        return False
    return _matches(names, _allowed_names())


def current_audio_names() -> tuple[str, str]:
    devices = sd.query_devices()
    input_index, output_index = sd.default.device
    input_name = _device_name(devices, input_index)
    output_name = _device_name(devices, output_index)
    return input_name, output_name


def current_local_wake_allowed() -> bool:
    input_name, output_name = current_audio_names()
    return local_wake_allowed(input_name, output_name)


def voice_intent_label(input_name: str = "", output_name: str = "") -> str:
    names = _joined_names(input_name, output_name)
    if _matches(names, _blocked_names()):
        return "no_voice_wake"
    if _matches(names, _allowed_names()):
        return "sony_headphone_maya"
    return "no_voice_wake"


def _allowed_names() -> list[str]:
    return normalized_names(runtime_config().preferred_audio_output_names)


def _blocked_names() -> list[str]:
    return normalized_names(runtime_config().blocked_audio_output_names)


def _matches(names: str, needles: list[str]) -> bool:
    return any(needle in names for needle in needles)


def _joined_names(input_name: str, output_name: str) -> str:
    return f"{input_name} {output_name}".casefold()


def _device_name(devices, index) -> str:
    try:
        if index is None or int(index) < 0:
            return ""
        return str(devices[int(index)].get("name", ""))
    except Exception:
        return ""
