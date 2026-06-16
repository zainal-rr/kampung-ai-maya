from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_core.provider_capabilities import CAPABILITIES, capability_context, review_triggers


def main() -> None:
    required = {"sight", "sight_premium", "mind", "steward", "artisan", "pulse"}
    _require(required.issubset(CAPABILITIES), "missing provider capabilities")
    _require(CAPABILITIES["sight"].can_write_memory, "Gemini should own memory first pass")
    _require(CAPABILITIES["sight_premium"].default_model == "gemini-3.5-flash", "premium Gemini model wrong")
    _require(not CAPABILITIES["steward"].can_write_memory, "Claude should review, not write memory")
    _require(CAPABILITIES["artisan"].owner == "The Artisan", "Artisan owner wrong")
    _require(CAPABILITIES["artisan"].default_model == "codex", "Artisan default engine wrong")
    _require("/complex" in CAPABILITIES["mind"].triggers, "GPT complex trigger missing")
    _require("review" in review_triggers(), "Claude review trigger missing")
    context = capability_context()
    _require("The Steward" in context and "The Sight" in context, "capability context incomplete")
    print("provider_capabilities_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
