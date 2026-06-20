from __future__ import annotations

_LAST_OPEN_RESULT: dict = {}


def extension_last_open_result() -> dict:
    return dict(_LAST_OPEN_RESULT)


def reset_extension_last_open_result() -> None:
    global _LAST_OPEN_RESULT
    _LAST_OPEN_RESULT = {}


def remember_extension_open_result(result: dict) -> None:
    global _LAST_OPEN_RESULT
    _LAST_OPEN_RESULT = dict(result or {})
