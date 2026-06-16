from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from memory_perspective import normalize_user_perspective_memory


def main() -> None:
    _require(
        normalize_user_perspective_memory("This girl is my fiancee") == "This girl is Zainal's fiancee",
        "fiancee perspective not normalized",
    )
    _require(
        normalize_user_perspective_memory("remember my wife likes coffee") == "remember Zainal's wife likes coffee",
        "wife perspective not normalized",
    )
    _require(
        normalize_user_perspective_memory("my regression fruit is mangosteen") == "my regression fruit is mangosteen",
        "non-relationship memory should not be rewritten",
    )
    print("memory_perspective_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
