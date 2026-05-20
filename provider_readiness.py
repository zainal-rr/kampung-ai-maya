from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


KEYS = (
    ("GOOGLE_API_KEY", "Gemini Flash, screen, sight, Omi, memory shaping"),
    ("KIMI_API_KEY", "The Artisan coding and repo maintenance"),
    ("OPENAI_API_KEY", "GPT-5.5 complex lane through /complex"),
    ("ANTHROPIC_API_KEY", "Claude Sonnet steward review lane"),
    ("XAI_API_KEY", "Grok pulse, Ara TTS, xAI STT, voice agent"),
    ("TELEGRAM_BOT_TOKEN", "Telegram channel"),
)
MODEL_VARS = (
    ("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
    ("GEMINI_PRO_MODEL", "gemini-3.1-pro"),
    ("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
    ("OPENAI_COMPLEX_REASONING_EFFORT", "xhigh"),
    ("CLAUDE_STEWARD_MODEL", "claude-sonnet-4-6"),
    ("XAI_VOICE_AGENT_MODEL", "grok-voice-think-fast-1.0"),
    ("XAI_VOICE_AGENT_VOICE", "ara"),
)


def provider_readiness_text() -> str:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    key_lines = [f"{idx}) {name}: {_state(name)} for {purpose}" for idx, (name, purpose) in enumerate(KEYS, start=1)]
    model_lines = [
        f"{idx}) {name}: {os.getenv(name, default)}"
        for idx, (name, default) in enumerate(MODEL_VARS, start=1)
    ]
    gates = (
        "1) text gate: run provider_smoke.py --stage text --strict\n"
        "2) vision gate: run provider_smoke.py --stage vision --strict\n"
        "3) voice gate: run provider_smoke.py --stage voice --strict"
    )
    return (
        "Provider readiness:\n"
        + "\n".join(key_lines)
        + "\n\nModel settings:\n"
        + "\n".join(model_lines)
        + "\n\nLive test order:\n"
        + gates
    )


def _state(name: str) -> str:
    return "set" if os.getenv(name) else "missing"


if __name__ == "__main__":
    print(provider_readiness_text())
