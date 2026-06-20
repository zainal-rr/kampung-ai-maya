from __future__ import annotations


def empty_request_reason(has_request: bool) -> str:
    """Return a mechanical reason for an empty tool argument.

    This guard intentionally receives only a boolean. It cannot inspect the
    request text, so it cannot become a semantic readiness checker.
    """

    return "" if has_request else "empty_request"
