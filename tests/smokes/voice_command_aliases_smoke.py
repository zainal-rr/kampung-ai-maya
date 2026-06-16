from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from voice_command_aliases import spoken_command_alias


def main() -> None:
    cases = {
        "make a complex plan for browser reliability and wait for approval": "/complex browser reliability and wait for approval",
        "complex route: diagnose why PowerPoint QA fails before patching": "/complex diagnose why powerpoint qa fails before patching",
        "think deeply about document continuity architecture": "/complex document continuity architecture",
        "prepare a checkpointed workflow for weekly memory safety": "/complex weekly memory safety",
        "make a skill for polished PowerPoint speaker notes": "/createskill polished powerpoint speaker notes",
        "make a proposed skill for PowerPoint visual taste": "/createskill powerpoint visual taste",
        "create skill for YouTube channel navigation": "/createskill youtube channel navigation",
        "can you create a browser research skill first and ask me before activating": "/createskill browser research",
    }
    for text, expected in cases.items():
        actual = spoken_command_alias(text, channel="telegram", input_type="text")
        _require(actual == expected, f"{text!r}: expected {expected!r}, got {actual!r}")
    print("voice_command_aliases_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
