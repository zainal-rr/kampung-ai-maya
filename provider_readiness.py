from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv


KEYS = (
    ("GOOGLE_API_KEY", "Gemini 3.1 Flash default, Gemini 3.5 Flash premium sight, Omi, memory shaping"),
    ("KIMI_API_KEY", "legacy Kimi only; retired from active coding"),
    ("OPENAI_API_KEY", "GPT-5.5 complex lane through /complex"),
    ("ANTHROPIC_API_KEY", "Claude Opus steward review lane"),
    ("XAI_API_KEY", "Grok pulse, Ara TTS, xAI STT, voice agent"),
    ("TELEGRAM_BOT_TOKEN", "Telegram channel"),
)
MODEL_VARS = (
    ("GEMINI_FLASH_MODEL", "gemini-3.1-flash"),
    ("GEMINI_PREMIUM_MODEL", "gemini-3.5-flash"),
    ("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
    ("OPENAI_COMPLEX_REASONING_EFFORT", "medium"),
    ("CLAUDE_STEWARD_MODEL", "claude-opus-4-8"),
    ("XAI_VOICE_AGENT_MODEL", "grok-voice-think-fast-1.0"),
    ("XAI_VOICE_AGENT_VOICE", "ara"),
)
LOCAL_TOOLS = (
    ("codex", "Codex for The Artisan"),
    ("blender", "Blender for Maker/3D export"),
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
        "3) voice gate: run provider_smoke.py --stage voice --strict\n"
        "4) artisan gate: run artisan_runner_smoke.py"
    )
    tool_lines = [f"{idx}) {tool}: {_tool_state(tool)} for {purpose}" for idx, (tool, purpose) in enumerate(LOCAL_TOOLS, start=1)]
    return (
        "Provider readiness:\n"
        + "\n".join(key_lines)
        + "\n\nModel settings:\n"
        + "\n".join(model_lines)
        + "\n\nLocal tools:\n"
        + "\n".join(tool_lines)
        + "\n\nLive test order:\n"
        + gates
    )


def _state(name: str) -> str:
    return "set" if os.getenv(name) else "missing"


def _tool_state(name: str) -> str:
    if shutil.which(name):
        if name == "codex":
            return _codex_auth_state()
        return "available"
    if name == "blender" and Path("/Applications/Blender.app").exists():
        return "available"
    return "missing"


def _codex_auth_state() -> str:
    try:
        proc = subprocess.run(
            ["codex", "login", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return "installed, auth unknown"
    output = f"{proc.stdout}\n{proc.stderr}".lower()
    if "logged in using chatgpt" in output:
        return "logged in using ChatGPT"
    if "logged in" in output:
        return "logged in, but not confirmed as ChatGPT subscription auth"
    return "installed, auth unknown"


if __name__ == "__main__":
    print(provider_readiness_text())
