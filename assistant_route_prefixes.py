from __future__ import annotations

COMPLEX_ROUTE_PREFIX = "[complex]"
SIGHT_ROUTE_PREFIX = "[sight]"


def is_complex_route(text: str) -> bool:
    return text.lower().startswith(COMPLEX_ROUTE_PREFIX)


def is_sight_route(text: str) -> bool:
    return text.lower().startswith(SIGHT_ROUTE_PREFIX)


def complex_payload(text: str) -> str:
    return text[len(COMPLEX_ROUTE_PREFIX):].strip()


def sight_payload(text: str) -> str:
    return text[len(SIGHT_ROUTE_PREFIX):].strip()
