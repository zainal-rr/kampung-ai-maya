# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

import asyncio
import os
import shutil
import subprocess

from dotenv import load_dotenv

from audio_devices import bin_path, resolve_audio_input
from speech_input import detect_avfoundation_audio_devices

load_dotenv()


def check_command(name: str) -> str | None:
    return shutil.which(name)


async def try_record(audio_device: str, seconds: int = 1) -> tuple[bool, str]:
    process = await asyncio.create_subprocess_exec(
        bin_path("ffmpeg"),
        "-y",
        "-f",
        "avfoundation",
        "-i",
        audio_device,
        "-t",
        str(seconds),
        "-ac",
        "1",
        "-ar",
        "16000",
        "/tmp/kampung-ai-audio-probe.wav",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    message = stderr.decode("utf-8", errors="ignore").strip()
    return process.returncode == 0, message


async def main():
    print("== Kampung AI Audio Probe ==")
    print(f"ffmpeg: {check_command('ffmpeg')}")
    print(f"whisper: {check_command('whisper')}")

    devices = detect_avfoundation_audio_devices()
    print(f"visible_avfoundation_audio_devices: {devices}")

    raw_targets = (
        os.getenv("IMAC_AUDIO_INPUT_NAMES")
        or os.getenv("IMAC_AUDIO_INPUTS")
        or os.getenv("IMAC_AUDIO_INPUT", ":0")
    )
    targets = [resolve_audio_input(target) for target in raw_targets.split(",") if target.strip()]
    print(f"configured_inputs: {targets}")

    ok = False
    for target in targets:
        ok, details = await try_record(target)
        print(f"record_test_{target}_ok: {ok}")
        if details:
            print(f"record_test_{target}_details:")
            print(details)
        if ok:
            break

    if ok:
        print("recommended_imac_input_mode=mic")
    elif devices:
        print("recommended_action=adjust IMAC_AUDIO_INPUT to a valid visible device index")
    else:
        print("recommended_action=grant microphone access and re-run this probe")
        print("recommended_imac_input_mode=manual")


if __name__ == "__main__":
    asyncio.run(main())
