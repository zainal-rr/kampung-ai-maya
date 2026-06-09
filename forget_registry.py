from __future__ import annotations

from typing import Awaitable, Callable

ForgetHandler = Callable[[str, str], Awaitable[int]]

# Ordered registry of every store /forget must cover. The safety property:
# a memory store that is not registered here cannot be forgotten, so any new
# store MUST register a handler (and add an over/under-deletion case to
# memory_recall_eval.py). Order matters: fuzzy matching captures related
# tokens from rows before the LIKE-based handlers delete them.
_HANDLERS: list[tuple[str, str, ForgetHandler]] = []


def register_forget_handler(key: str, label: str, handler: ForgetHandler) -> None:
    if any(existing_key == key for existing_key, _label, _handler in _HANDLERS):
        raise ValueError(f"Forget handler already registered: {key}")
    _HANDLERS.append((key, label, handler))


def registered_forget_handlers() -> list[tuple[str, str, ForgetHandler]]:
    return list(_HANDLERS)


async def run_forget_handlers(db_path: str, query: str) -> dict[str, int]:
    """Run every registered handler in registration order.

    Returns an ordered mapping of handler key to deleted-row count. Handlers
    own their own connections and commits; a handler that raises stops the
    run (forgetting must not half-succeed silently).
    """
    counts: dict[str, int] = {}
    for key, _label, handler in _HANDLERS:
        counts[key] = int(await handler(db_path, query))
    return counts


def handler_labels() -> dict[str, str]:
    return {key: label for key, label, _handler in _HANDLERS}
