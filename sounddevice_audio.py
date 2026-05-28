from __future__ import annotations

from dataclasses import dataclass
import os
import time

import sounddevice as sd


DEFAULT_INPUT_NAMES = "Zainal’s Headphone,iMac Microphone"
DEFAULT_OUTPUT_NAMES = "Zainal’s Headphone,Sony WH-1000XM5,iMac Speakers"


@dataclass(frozen=True)
class OutputResolution:
    device: int | None
    label: str
    missing_configured: tuple[str, ...] = ()
    used_default_fallback: bool = False


def resolve_sounddevice_input(name: str | None = None):
    target = name or _first_name(
        os.getenv("IMAC_AUDIO_INPUT_NAMES")
        or os.getenv("IMAC_AUDIO_INPUTS")
        or os.getenv("IMAC_AUDIO_INPUT")
        or DEFAULT_INPUT_NAMES
    )
    return _resolve_device(target, input_required=True)


def resolve_sounddevice_output(name: str | None = None):
    target = name or _first_name(os.getenv("IMAC_AUDIO_OUTPUT_NAMES") or os.getenv("IMAC_AUDIO_OUTPUT") or DEFAULT_OUTPUT_NAMES)
    return _resolve_device(target, output_required=True)


def configured_output_names() -> list[str]:
    raw = os.getenv("IMAC_AUDIO_OUTPUT_NAMES") or os.getenv("IMAC_AUDIO_OUTPUT") or DEFAULT_OUTPUT_NAMES
    return [part.strip() for part in raw.split(",") if part.strip()]


def resolve_first_output_name() -> tuple[int | None, str]:
    result = resolve_first_output()
    return result.device, result.label


def resolve_first_output() -> OutputResolution:
    result = _resolve_first_output_once()
    if result.device is not None and not result.used_default_fallback:
        return result
    if result.missing_configured:
        refresh_sounddevice_hostapi()
        time.sleep(0.05)
        retry = _resolve_first_output_once()
        if retry.device is not None and not retry.used_default_fallback:
            return retry
        if retry.device is None or retry.used_default_fallback:
            return retry
    return result


def _resolve_first_output_once() -> OutputResolution:
    missing = []
    for name in configured_output_names():
        device = resolve_sounddevice_output(name)
        if device is not None:
            return OutputResolution(device, name, tuple(missing))
        missing.append(name)
    if os.getenv("IMAC_AUDIO_ALLOW_DEFAULT_OUTPUT_FALLBACK", "1") == "0":
        return OutputResolution(None, ", ".join(configured_output_names()), tuple(missing))
    default = resolve_default_output()
    if default[0] is not None:
        return OutputResolution(default[0], default[1], tuple(missing), used_default_fallback=True)
    return OutputResolution(None, ", ".join(configured_output_names()), tuple(missing))


def refresh_sounddevice_hostapi() -> None:
    try:
        sd._terminate()
        sd._initialize()
    except Exception:
        return


def output_device_snapshot() -> list[str]:
    try:
        return [
            f"{index}:{device.get('name')} out={device.get('max_output_channels')}"
            for index, device in enumerate(sd.query_devices())
            if int(device.get("max_output_channels", 0)) > 0
        ]
    except Exception as exc:
        return [f"device query failed: {exc}"]


def resolve_default_output() -> tuple[int | None, str]:
    try:
        index = sd.default.device[1]
        if index is None or int(index) < 0:
            return None, "macOS default output"
        device = sd.query_devices()[int(index)]
        if int(device.get("max_output_channels", 0)) < 1:
            return None, "macOS default output"
        return int(index), f"macOS default output: {device.get('name', index)}"
    except Exception:
        return None, "macOS default output"


def _resolve_device(target: str | None, input_required: bool = False, output_required: bool = False):
    if not target:
        return None
    clean = target.strip()
    if not clean:
        return None
    if clean.startswith(":"):
        clean = clean[1:]
    if clean.isdigit():
        return int(clean)
    lowered = _normalize_name(clean)
    devices = sd.query_devices()
    for index, device in enumerate(devices):
        if _matches(device, lowered, input_required, output_required, exact=True):
            return index
    for index, device in enumerate(devices):
        if _matches(device, lowered, input_required, output_required, exact=False):
            return index
    return None


def _matches(device, target: str, input_required: bool, output_required: bool, exact: bool) -> bool:
    name = _normalize_name(str(device.get("name", "")))
    if input_required and int(device.get("max_input_channels", 0)) < 1:
        return False
    if output_required and int(device.get("max_output_channels", 0)) < 1:
        return False
    return name == target if exact else target in name


def _normalize_name(value: str) -> str:
    return (
        value.casefold()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("´", "'")
    )


def _first_name(raw: str | None) -> str | None:
    if not raw:
        return None
    return next((part.strip() for part in raw.split(",") if part.strip()), None)
