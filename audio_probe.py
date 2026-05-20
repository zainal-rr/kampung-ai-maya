import asyncio
import os
import shutil
import subprocess

from speech_input import detect_avfoundation_audio_devices


def check_command(name: str) -> str | None:
    return shutil.which(name)


async def try_record(audio_device: str, seconds: int = 1) -> tuple[bool, str]:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
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

    target = os.getenv("IMAC_AUDIO_INPUT", ":0")
    print(f"configured_input: {target}")

    ok, details = await try_record(target)
    print(f"record_test_ok: {ok}")
    if details:
        print("record_test_details:")
        print(details)

    if ok:
        print("recommended_imac_input_mode=mic")
    elif devices:
        print("recommended_action=adjust IMAC_AUDIO_INPUT to a valid visible device index")
    else:
        print("recommended_action=grant microphone access and re-run this probe")
        print("recommended_imac_input_mode=manual")


if __name__ == "__main__":
    asyncio.run(main())
