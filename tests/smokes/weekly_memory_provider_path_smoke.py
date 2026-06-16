from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import os

from weekly_memory_providers import WeeklyClaudeReviewer, WeeklyGeminiDistiller, _weekly_gemini_model


def main() -> None:
    os.environ["GEMINI_FLASH_MODEL"] = "gemini-flash-test"
    os.environ["GEMINI_PREMIUM_MODEL"] = "gemini-premium-test"
    os.environ.pop("WEEKLY_MEMORY_FORCE_PREMIUM", None)
    os.environ["WEEKLY_MEMORY_PREMIUM_CHARS"] = "40"
    _require(_weekly_gemini_model("normal week summary") == "gemini-flash-test", "normal week should use Gemini Flash")
    _require(_weekly_gemini_model("x" * 80) == "gemini-premium-test", "dense week should use Gemini premium")
    _require(_weekly_gemini_model("ambiguous conflicting preference") == "gemini-premium-test", "ambiguous week should use premium")
    os.environ["WEEKLY_MEMORY_FORCE_PREMIUM"] = "1"
    _require(_weekly_gemini_model("normal week summary") == "gemini-premium-test", "force premium flag failed")
    distiller = WeeklyGeminiDistiller("dummy")
    reviewer = WeeklyClaudeReviewer.__new__(WeeklyClaudeReviewer)
    _require(distiller.usage_lane == "gemini_flash_text_calls", "distiller usage lane default wrong")
    _require(reviewer.usage_lane == "claude_steward_calls", "reviewer usage lane wrong")
    print("weekly_memory_provider_path_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
