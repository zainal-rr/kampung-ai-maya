from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_core.safety_action_commands import safety_action_reply


def main() -> None:
    bank = safety_action_reply("use my bank details for the tracker")
    _require(bank is not None and "sensitive private information" in bank.lower(), "bank details use should be blocked")
    key = safety_action_reply("save this private key for me")
    _require(key is not None and "sensitive private information" in key.lower(), "private key save should be blocked")
    publish = safety_action_reply("publish the repo publicly with secrets")
    _require(publish is not None and "sensitive private information" in publish.lower(), "publishing secrets should be blocked")
    guidance = safety_action_reply("make a password policy checklist")
    _require(guidance is None, "safe password guidance should not be blocked")
    print("safety_action_commands_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
