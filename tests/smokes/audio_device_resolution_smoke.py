from __future__ import annotations

from audio_devices import list_audio_devices, resolve_audio_input


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    _require(resolve_audio_input(":5") == ":5", "colon index did not pass through")
    _require(resolve_audio_input("5") == ":5", "numeric index did not normalize")
    devices = list_audio_devices()
    if devices:
        first = devices[0]
        _require(resolve_audio_input(first.name) == first.ffmpeg_input, "name did not resolve")
    print("audio_device_resolution_smoke: ok")


if __name__ == "__main__":
    main()
