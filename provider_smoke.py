from __future__ import annotations

import asyncio
import argparse
import base64
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

async def main() -> None:
    args = _args()
    print("== Kampung AI Provider Smoke ==")
    print(f"environment: {_load_environment()}")
    if dependency_error := _dependency_error():
        print(dependency_error)
        if args.strict:
            raise SystemExit(1)
        return
    print(_key_status())
    results = await _run_stage(args.stage)
    for name, result in results.items():
        print(f"{name}: {result}")
    if args.strict and not _all_ok(results):
        raise SystemExit(1)


async def _run_stage(stage: str) -> dict[str, str]:
    text_checks = {
        "gemini": check_gemini,
        "gpt_5_5": check_openai,
        "claude_steward": check_claude,
        "grok": check_grok,
    }
    vision_checks = {"gemini_vision": check_gemini_vision}
    voice_checks = {"ara_tts": check_tts, "xai_stt": check_xai_stt}
    groups = []
    if stage in {"all", "text"}:
        groups.append(text_checks)
    if stage in {"all", "vision"}:
        groups.append(vision_checks)
    if stage in {"all", "voice"}:
        groups.append(voice_checks)
    results = {}
    for group in groups:
        for name, check in group.items():
            results[name] = await check()
    return results


async def check_gemini() -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "skipped (missing GOOGLE_API_KEY)"
    try:
        from models import TheSenses
        reply = await TheSenses(api_key).chat([{"role": "user", "content": "Reply with exactly: sight ok"}])
        return _ok(reply, "sight ok")
    except Exception as exc:
        return f"error ({exc})"


async def check_openai() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "skipped (missing OPENAI_API_KEY)"
    try:
        from models import TheMind
        reply = await TheMind(api_key).chat([{"role": "user", "content": "Reply with exactly: mind ok"}])
        return _ok(reply, "mind ok")
    except Exception as exc:
        return f"error ({exc})"


async def check_claude() -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "skipped (missing ANTHROPIC_API_KEY)"
    try:
        from models import TheSteward
        reply = await TheSteward(api_key).chat([{"role": "user", "content": "Reply with exactly: steward ok"}])
        return _ok(reply, "steward ok")
    except Exception as exc:
        return f"error ({exc})"


async def check_grok() -> str:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        return "skipped (missing XAI_API_KEY)"
    try:
        from models import TheNews
        reply = await TheNews(api_key).chat([{"role": "user", "content": "Reply with exactly: pulse ok"}])
        return _ok(reply, "pulse ok")
    except Exception as exc:
        return f"error ({exc})"


async def check_tts() -> str:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        return "skipped (missing XAI_API_KEY; macOS fallback is not counted as Ara)"
    sample = "Maya audio check."
    try:
        from voice import VoiceNode
        voice = VoiceNode(os.getenv("KAMPUNG_DB_PATH"))
        audio_path = await voice.render_audio_file(sample)
        exists = audio_path.exists()
        await voice.cleanup_file(audio_path)
        return "ok" if exists else "error (no audio file created)"
    except Exception as exc:
        return f"error ({exc})"


async def check_gemini_vision() -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "skipped (missing GOOGLE_API_KEY)"
    try:
        from models import TheSenses
        prompt = "Describe this test image with exactly: vision ok"
        reply = await TheSenses(api_key).describe_image(_tiny_jpeg(), prompt)
        return _ok(reply, "vision ok")
    except Exception as exc:
        return f"error ({exc})"


async def check_xai_stt() -> str:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        return "skipped (missing XAI_API_KEY)"
    sample_path = await asyncio.to_thread(_make_sample_wav)
    try:
        from speech_input import xai_transcribe_file
        transcript = await asyncio.to_thread(xai_transcribe_file, api_key, sample_path, "en")
        return _ok_any(transcript, ("maya speech check", "my speech check", "speech check"))
    except Exception as exc:
        return f"error ({exc})"
    finally:
        shutil.rmtree(sample_path.parent, ignore_errors=True)


def _make_sample_wav() -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="maya-smoke-"))
    aiff_path = tmp_dir / "sample.aiff"
    wav_path = tmp_dir / "sample.wav"
    subprocess.run(
        ["say", "-v", os.getenv("MACOS_SAY_VOICE_EN", "Flo (English (US))"), "-o", str(aiff_path), "maya speech check"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(aiff_path), str(wav_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if aiff_path.exists():
        aiff_path.unlink()
    return wav_path


def _ok(reply: str, expected: str) -> str:
    text = " ".join(reply.split())
    if not text:
        return "error (empty response)"
    if expected.lower() not in text.lower():
        return f"unexpected ({text[:80]})"
    return f"ok ({text[:80]})"


def _ok_any(reply: str, expected_options: tuple[str, ...]) -> str:
    text = " ".join(reply.split())
    if not text:
        return "error (empty response)"
    lowered = text.lower()
    if not any(expected.lower() in lowered for expected in expected_options):
        return f"unexpected ({text[:80]})"
    return f"ok ({text[:80]})"


def _all_ok(results: dict[str, str]) -> bool:
    return bool(results) and all(value.startswith("ok ") or value == "ok" for value in results.values())


def _tiny_jpeg() -> bytes:
    from io import BytesIO

    try:
        from PIL import Image, ImageDraw
    except Exception:
        raw = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Ar//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IR//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QP//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QP//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QP//Z"
        return base64.b64decode(raw)
    image = Image.new("RGB", (64, 64), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill=(20, 120, 240))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _load_environment() -> str:
    try:
        from dotenv import load_dotenv
    except Exception:
        return "using shell environment (python-dotenv unavailable)"
    env_path = Path(__file__).resolve().parent / ".env"
    loaded = load_dotenv(env_path)
    return f"loaded {env_path}" if loaded else "using shell environment"


def _key_status() -> str:
    names = ("GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY")
    parts = [f"{name}={'set' if os.getenv(name) else 'missing'}" for name in names]
    return "keys: " + ", ".join(parts)


def _dependency_error() -> str | None:
    try:
        import dotenv  # noqa: F401
        import openai  # noqa: F401
        import httpx  # noqa: F401
        from google import genai  # noqa: F401
    except Exception:
        return (
            "Missing project dependencies in this interpreter. "
            f"Run with /Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python {Path(sys.argv[0]).name}"
        )
    return None


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Kampung AI live provider smoke checks.")
    parser.add_argument("--stage", choices=("all", "text", "vision", "voice"), default="all")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless every selected check is ok.")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main())
