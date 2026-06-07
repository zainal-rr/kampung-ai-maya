from __future__ import annotations

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
