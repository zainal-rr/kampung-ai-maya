import os
import shutil
import json
import asyncio
from pathlib import Path

from code_health import collect_code_health, format_code_health
from dotenv import load_dotenv
from provider_readiness import provider_readiness_text
from speech_input import detect_avfoundation_audio_devices
from weekly_memory_store import latest_weekly_summary


load_dotenv()

REQUIRED_VARS = ["GOOGLE_API_KEY", "KIMI_API_KEY"]
OPTIONAL_VARS = ["TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY"]


def present(name: str) -> bool:
    return bool(os.getenv(name))


def print_var_status() -> None:
    print("== Environment ==")
    for name in REQUIRED_VARS:
        print(f"{name}: {'ok' if present(name) else 'missing'}")
    for name in OPTIONAL_VARS:
        print(f"{name}: {'set' if present(name) else 'not set'}")


def print_host_status() -> None:
    print("\n== Host Mode ==")
    print("ENABLE_IMAC_CHANNEL:", os.getenv("ENABLE_IMAC_CHANNEL", "0"))
    print("TELEGRAM_VOICE_REPLIES:", os.getenv("TELEGRAM_VOICE_REPLIES", "1"))
    print("TELEGRAM_REQUIRE_ARA:", os.getenv("TELEGRAM_REQUIRE_ARA", "1"))
    print("TELEGRAM_VOICE_LOCKED:", os.getenv("TELEGRAM_VOICE_LOCKED", "1"))
    print("ENABLE_AGENT_RUNTIME:", os.getenv("ENABLE_AGENT_RUNTIME", "1"))
    print("ENABLE_ROUTINES:", os.getenv("ENABLE_ROUTINES", "1"))
    print("ENABLE_OMI_ADAPTER:", os.getenv("ENABLE_OMI_ADAPTER", "0"))
    print("ENABLE_MUDRA_ADAPTER:", os.getenv("ENABLE_MUDRA_ADAPTER", "0"))
    print("ENABLE_EXTERNAL_CAMERA_ADAPTER:", os.getenv("ENABLE_EXTERNAL_CAMERA_ADAPTER", "0"))
    print("ENABLE_VISION_CAMERA:", os.getenv("ENABLE_VISION_CAMERA", "0"))
    print("MAYA_EYE_PREVIEW:", os.getenv("MAYA_EYE_PREVIEW", "0"))
    print("MAYA_SCREEN_SESSION_MINUTES:", os.getenv("MAYA_SCREEN_SESSION_MINUTES", "10"))
    print("VISION_CAMERA_EFFECTIVE:", vision_camera_effective())
    print("IMAC_INPUT_MODE:", os.getenv("IMAC_INPUT_MODE", "auto"))
    print("IMAC_AUDIO_INPUT:", os.getenv("IMAC_AUDIO_INPUT", ":0"))
    print("IMAC_AUDIO_INPUTS:", os.getenv("IMAC_AUDIO_INPUTS", ""))
    print("IMAC_AUDIO_INPUT_NAMES:", os.getenv("IMAC_AUDIO_INPUT_NAMES", ""))
    print("MACOS_SAY_VOICE:", os.getenv("MACOS_SAY_VOICE", "Samantha"))
    print("MAYA_WAKE_PHRASES:", os.getenv("MAYA_WAKE_PHRASES", "hey maya,good morning maya,hello maya,maya"))
    print("MAYA_WAKE_WINDOW_SECONDS:", os.getenv("MAYA_WAKE_WINDOW_SECONDS", "5"))
    print("ENABLE_XAI_VOICE_AGENT:", os.getenv("ENABLE_XAI_VOICE_AGENT", "0"))
    print("XAI_VOICE_AGENT_MODE:", os.getenv("XAI_VOICE_AGENT_MODE", "stub"))
    print("XAI_VOICE_AGENT_IDLE_SECONDS:", os.getenv("XAI_VOICE_AGENT_IDLE_SECONDS", "5"))
    print("XAI_VOICE_AGENT_MODEL:", os.getenv("XAI_VOICE_AGENT_MODEL", "grok-voice-think-fast-1.0"))
    print("XAI_VOICE_AGENT_VOICE:", os.getenv("XAI_VOICE_AGENT_VOICE", "ara"))
    print("OPENAI_COMPLEX_REASONING_EFFORT:", os.getenv("OPENAI_COMPLEX_REASONING_EFFORT", "xhigh"))
    print("CLAUDE_STEWARD_MODEL:", os.getenv("CLAUDE_STEWARD_MODEL", "claude-sonnet-4-6"))
    print("GEMINI_FLASH_MODEL:", os.getenv("GEMINI_FLASH_MODEL", "gemini-3.1-flash"))
    print("GEMINI_PREMIUM_MODEL:", os.getenv("GEMINI_PREMIUM_MODEL", "gemini-3.5-flash"))
    print("GEMINI_IMAGE_MODEL:", os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"))
    print("ENABLE_GEMINI_IMAGE_GENERATION:", os.getenv("ENABLE_GEMINI_IMAGE_GENERATION", "0"))
    print("MAYA_DISABLE_IMAC_CAMERA:", os.getenv("MAYA_DISABLE_IMAC_CAMERA", "1"))
    print("MAYA_EXTERNAL_CAMERA_NAME:", os.getenv("MAYA_EXTERNAL_CAMERA_NAME", "Cisco Desk Camera 4K"))
    print("MAYA_EXTERNAL_CAMERA_INDEX:", os.getenv("MAYA_EXTERNAL_CAMERA_INDEX", "0"))
    print("MAYA_IMAC_CAMERA_INDEX:", os.getenv("MAYA_IMAC_CAMERA_INDEX", "1"))
    print("MAYA_CAMERA_BLOCKED_DARKNESS_THRESHOLD:", os.getenv("MAYA_CAMERA_BLOCKED_DARKNESS_THRESHOLD", "8"))
    print("MAYA_CAMERA_BLOCKED_FLAT_BRIGHTNESS_MAX:", os.getenv("MAYA_CAMERA_BLOCKED_FLAT_BRIGHTNESS_MAX", "45"))
    print("MAYA_CAMERA_BLOCKED_STDDEV_THRESHOLD:", os.getenv("MAYA_CAMERA_BLOCKED_STDDEV_THRESHOLD", "3"))
    print("MUDRA_ACTIVATION_DISTANCE_METRES:", os.getenv("MUDRA_ACTIVATION_DISTANCE_METRES", "1.0"))


def print_tool_status() -> None:
    print("\n== Local Tools ==")
    for tool in ["ffmpeg", "whisper"]:
        print(f"{tool}: {shutil.which(tool) or 'missing'}")


def vision_camera_effective() -> str:
    requested = os.getenv("ENABLE_VISION_CAMERA", "0") == "1"
    local_enabled = (
        os.getenv("ENABLE_IMAC_CHANNEL", "0") == "1"
        or os.getenv("ENABLE_EXTERNAL_CAMERA_ADAPTER", "0") == "1"
    )
    return "1" if requested and local_enabled else "0"


def print_audio_status() -> None:
    print("\n== Audio ==")
    devices = detect_avfoundation_audio_devices()
    print("visible_avfoundation_audio_devices:", devices)
    if devices:
        print("audio_status: mic path may be available")
    else:
        print("audio_status: no visible mic devices, manual mode recommended for now")


def print_runtime_status() -> None:
    print("\n== Runtime ==")
    health_path = Path("logs/health.json")
    service_path = Path.home() / "Library" / "LaunchAgents" / "com.kampungai.maya.plist"
    print("launch_agent:", "present" if service_path.exists() else "missing")
    if not health_path.exists():
        print("health_snapshot: missing")
        return
    payload = json.loads(health_path.read_text(encoding="utf-8"))
    print("health_timestamp:", payload.get("timestamp", "unknown"))
    print("task_counts:", payload.get("task_counts", {}))
    print("routine_count:", payload.get("routine_count", 0))


def print_code_health() -> None:
    print("\n== Code Health ==")
    health = collect_code_health(Path(__file__).resolve().parent)
    print(format_code_health(health))


def print_provider_status() -> None:
    print("\n== Provider Readiness ==")
    print(provider_readiness_text())


def print_weekly_memory_status() -> None:
    print("\n== Weekly Memory ==")
    db_path = os.getenv("KAMPUNG_DB_PATH", "session_history.db")
    try:
        latest = asyncio.run(latest_weekly_summary(db_path))
    except Exception as exc:
        print(f"weekly_summary: unavailable ({exc})")
        return
    if not latest:
        print("weekly_summary: missing")
        print("recommendation: run ./venv/bin/python weekly_memory.py --save")
        return
    print("weekly_summary: present")
    print("run_key:", latest.get("run_key", "unknown"))
    print("source:", latest.get("source", "unknown"))
    print("created_at:", latest.get("created_at", "unknown"))


def print_recommendation() -> None:
    print("\n== Recommendation ==")
    if not all(present(name) for name in REQUIRED_VARS):
        print("Fill required API keys before starting the full system.")
        return

    if os.getenv("ENABLE_IMAC_CHANNEL", "0") != "1":
        print("Telegram-only or remote mode is ready. Enable the iMac channel when you want local interaction.")
        return

    devices = detect_avfoundation_audio_devices()
    if devices:
        print("Run the iMac channel in auto or mic mode and test local speech input.")
    else:
        print("Use IMAC_INPUT_MODE=manual until Terminal has microphone access on the spare iMac.")


if __name__ == "__main__":
    print("== Kampung AI Doctor ==")
    print_var_status()
    print_host_status()
    print_tool_status()
    print_audio_status()
    print_runtime_status()
    print_provider_status()
    print_weekly_memory_status()
    print_code_health()
    print_recommendation()
