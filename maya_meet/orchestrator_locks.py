from __future__ import annotations

import asyncio


_MEET_LOCKS: dict[str, asyncio.Lock] = {}


def meet_lock(key: str) -> asyncio.Lock:
    return _MEET_LOCKS.setdefault(key, asyncio.Lock())
