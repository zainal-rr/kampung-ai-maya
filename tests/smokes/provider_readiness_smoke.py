from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from provider_readiness import provider_readiness_text
from telegram_channel import TelegramChannel
from telegram_commands import command_help, parse_command


def main() -> None:
    text = provider_readiness_text()
    _require(text.startswith("Provider readiness:"), "readiness title missing")
    for key in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY", "TELEGRAM_BOT_TOKEN"):
        _require(key in text, f"{key} missing from readiness")
    _require("CLAUDE_STEWARD_MODEL" in text, "Claude model setting missing")
    _require("provider_smoke.py --stage text --strict" in text, "text gate missing")
    _require("provider_smoke.py --stage vision --strict" in text, "vision gate missing")
    _require("provider_smoke.py --stage voice --strict" in text, "voice gate missing")
    _require(TelegramChannel._is_direct_command_reply(text), "provider readiness should be direct")
    _require(parse_command("/providers").name == "providers", "providers command did not parse")
    help_text = command_help()
    _require("/status" in help_text, "status missing from help")
    _require("/providers" in help_text, "providers alias missing from help")
    _require("/weekly" in help_text, "weekly alias missing from help")
    print("provider_readiness_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
