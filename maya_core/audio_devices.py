from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass

from maya_core.execution_broker import CommandSpec, run_command


@dataclass(frozen=True)
class AudioDevice:
    index: str
    name: str

    @property
    def ffmpeg_input(self) -> str:
        return f":{self.index}"


def bin_path(name: str) -> str:
    env_value = os.getenv(f"{name.upper()}_BIN")
    if env_value:
        return env_value
    return shutil.which(name) or f"/opt/homebrew/bin/{name}"


def list_audio_devices() -> list[AudioDevice]:
    result = run_command(CommandSpec(
        argv=(bin_path("ffmpeg"), "-f", "avfoundation", "-list_devices", "true", "-i", ""),
        profile="media",
        timeout=15,
        text=True,
        sandbox=False,
    )).to_completed_process()
    output = (result.stdout or "") + (result.stderr or "")
    in_audio = False
    devices: list[AudioDevice] = []
    for line in output.splitlines():
        if "AVFoundation audio devices:" in line:
            in_audio = True
            continue
        if not in_audio:
            continue
        match = re.search(r"\]\s+\[(\d+)\]\s+(.+)$", line)
        if match:
            devices.append(AudioDevice(match.group(1), match.group(2).strip()))
    return devices


def device_names() -> list[str]:
    return [device.index for device in list_audio_devices()]


def resolve_audio_input(spec: str) -> str:
    cleaned = spec.strip()
    if not cleaned:
        return cleaned
    if cleaned.startswith(":") or cleaned.isdigit():
        return cleaned if cleaned.startswith(":") else f":{cleaned}"
    lowered = cleaned.casefold()
    devices = list_audio_devices()
    for device in devices:
        if device.name.casefold() == lowered:
            return device.ffmpeg_input
    for device in devices:
        if lowered in device.name.casefold():
            return device.ffmpeg_input
    return cleaned


def resolve_first_named(names: list[str]) -> str | None:
    devices = list_audio_devices()
    for name in names:
        resolved = resolve_audio_input(name)
        if resolved.startswith(":") and any(d.ffmpeg_input == resolved for d in devices):
            return resolved
    return None


def has_audio_device_name(names: list[str]) -> bool:
    return resolve_first_named(names) is not None
