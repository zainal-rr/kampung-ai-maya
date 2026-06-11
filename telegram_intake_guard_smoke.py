"""Deterministic smoke for the Telegram intake guard.

Reproduces the 2026-06-10 live failure shape (messages visible, skill rows
written, no turn rows, no reply) and proves the guard closes it:

1. A turn row exists with status 'received' BEFORE the assistant runs.
2. A normal turn finalizes that same row to 'completed' (no duplicates).
3. A handler crash finalizes to 'failed' with the error class.
4. A task CANCELLATION (BaseException — the poller-conflict killer) still
   finalizes to 'failed' instead of vanishing.
5. The single-poller lock: second acquire refuses, release allows reacquire.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("TELEGRAM_ALLOWED_CHAT_IDS", "123")

from telegram_channel import TelegramChannel
from telegram_poller_lock import acquire_poller_lock
from telegram_turn_log import count_orphaned_received_turns, init_telegram_turn_log_db

import aiosqlite


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class _FakeBot:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, chat_id: int, text: str):
        self.sent.append(text)


class _Assistant:
    """Scripted assistant: behavior keyed by prompt content."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.voice = None

    async def handle_text(self, text: str, **_kwargs) -> str:
        if "crash" in text:
            raise RuntimeError("simulated handler crash after skill matching")
        if "cancel" in text:
            raise asyncio.CancelledError()
        if "probe receipt" in text:
            # Mid-handling probe: the received row must already exist.
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM telegram_turn_events WHERE status = 'received'"
                )
                row = await cursor.fetchone()
            _require(int(row[0]) == 1, "received row must exist BEFORE the assistant finishes")
        return "ok done"


def _update() -> SimpleNamespace:
    return SimpleNamespace(
        effective_message=SimpleNamespace(text="hello"),
        effective_chat=SimpleNamespace(id=123),
    )


async def _turn_rows(db_path: str) -> list[tuple[str, str, str]]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT prompt_preview, status, error FROM telegram_turn_events ORDER BY id"
        )
        return [(str(r[0]), str(r[1]), str(r[2])) for r in await cursor.fetchall()]


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-intake-guard-") as tmp:
        db_path = str(Path(tmp) / "t.db")
        await init_telegram_turn_log_db(db_path)
        channel = TelegramChannel("dummy-token", _Assistant(db_path))
        context = SimpleNamespace(bot=_FakeBot())

        # 1 + 2: receipt exists mid-handling; finalized to completed, one row.
        await channel._handle_text(_update(), context, "probe receipt please")
        rows = await _turn_rows(db_path)
        _require(len(rows) == 1, f"expected exactly one turn row, got {len(rows)}")
        _require(rows[0][1] == "completed", f"turn should finalize completed: {rows[0]}")
        print("  receipt-before-processing + finalize: ok")

        # 3: crash -> failed row, error recorded, exception still propagates.
        try:
            await channel._handle_text(_update(), context, "please crash now")
            _require(False, "crash should propagate")
        except RuntimeError:
            pass
        rows = await _turn_rows(db_path)
        _require(rows[-1][1] == "failed" and "RuntimeError" in rows[-1][2], f"crash row wrong: {rows[-1]}")
        print("  crash finalizes failed: ok")

        # 4: CancelledError (BaseException) -> failed row, not a vanish.
        try:
            await channel._handle_text(_update(), context, "please cancel mid-flight")
            _require(False, "cancellation should propagate")
        except asyncio.CancelledError:
            pass
        rows = await _turn_rows(db_path)
        _require(rows[-1][1] == "failed" and "CancelledError" in rows[-1][2], f"cancel row wrong: {rows[-1]}")
        _require(await count_orphaned_received_turns(db_path) == 0, "no orphaned received rows in clean runs")
        print("  cancellation finalizes failed (the live vanish case): ok")

        # 5: single-poller lock.
        with tempfile.TemporaryDirectory(prefix="maya-lock-") as lock_dir:
            first = acquire_poller_lock("smoke", lock_dir=lock_dir)
            _require(first is not None, "first lock acquire should succeed")
            second = acquire_poller_lock("smoke", lock_dir=lock_dir)
            _require(second is None, "second lock acquire must refuse (duplicate poller)")
            first.release()
            third = acquire_poller_lock("smoke", lock_dir=lock_dir)
            _require(third is not None, "lock must be reacquirable after release")
            third.release()
        print("  single-poller lock: ok")

    print("telegram_intake_guard_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
