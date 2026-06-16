# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

from maya_core.assistant_command_helpers import confirmation_decision


def main() -> None:
    _require(confirmation_decision("yes") == "approve", "plain yes should approve")
    _require(confirmation_decision("okay") == "approve", "plain okay should approve")
    _require(confirmation_decision("okay cakap malay") is None, "language request should not approve")
    _require(confirmation_decision("okay wait what is quantum computing") is None, "question should not approve")
    _require(confirmation_decision("okay wait change it to two person now") is None, "edit request should not approve")
    print("confirmation_decision_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
