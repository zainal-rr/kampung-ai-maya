from __future__ import annotations

import os

import aiosqlite


async def init_route_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS route_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_type TEXT NOT NULL,
                lane TEXT NOT NULL,
                reason TEXT NOT NULL,
                cost_recorded INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def record_route(
    db_path: str,
    input_type: str,
    lane: str,
    reason: str,
    cost_recorded: bool = False,
) -> None:
    await init_route_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO route_events (input_type, lane, reason, cost_recorded)
            VALUES (?, ?, ?, ?)
            """,
            (input_type, lane, reason, 1 if cost_recorded else 0),
        )
        await db.commit()


async def last_route_text(db_path: str) -> str:
    await init_route_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT input_type, lane, reason, cost_recorded, created_at
            FROM route_events
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    if not row:
        return "No route recorded yet."
    cost = "yes" if row["cost_recorded"] else "no"
    model = _model_for_lane(row["lane"])
    return (
        "Last route:\n"
        f"1) input: {row['input_type']}\n"
        f"2) lane: {row['lane']}\n"
        f"3) model: {model}\n"
        f"4) reason: {row['reason']}\n"
        f"5) cost recorded: {cost}\n"
        f"6) time: {row['created_at']}"
    )


def _model_for_lane(lane: str) -> str:
    lowered = lane.lower()
    prefix = ""
    claude_review = os.getenv("CLAUDE_STEWARD_MODEL", "claude-opus-4-8")
    if "xai stt" in lowered:
        prefix = f"{os.getenv('XAI_VOICE_TRANSCRIPTION_MODEL', 'grok-2-audio')} + "
    if "artisan" in lowered or "codex" in lowered:
        gemini = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")
        model = os.getenv("ARTISAN_CODEX_MODEL", "").strip()
        return f"{prefix}{gemini} + {model or 'codex'}".rstrip(" +")
    if "gemini" in lowered:
        if "claude" in lowered:
            gemini = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")
            return f"{prefix}{gemini} + {claude_review}"
        if "premium" in lowered or "pro" in lowered or "careful" in lowered:
            return f"{prefix}{os.getenv('GEMINI_PREMIUM_MODEL', 'gemini-3.5-flash')}"
        return f"{prefix}{os.getenv('GEMINI_FLASH_MODEL', 'gemini-3-flash-preview')}"
    if "gpt" in lowered:
        effort = os.getenv("OPENAI_COMPLEX_REASONING_EFFORT", "medium")
        return f"{prefix}gpt-5.5 ({effort})"
    if "codex" in lowered:
        return f"{prefix}{os.getenv('ARTISAN_CODEX_MODEL', '').strip() or 'codex'}".rstrip(" +")
    if "claude" in lowered or "steward" in lowered:
        return f"{prefix}{claude_review}"
    if "grok" in lowered or "pulse" in lowered:
        return f"{prefix}{os.getenv('XAI_TEXT_MODEL', 'grok-4.3')}"
    if prefix:
        return prefix.rstrip(" +")
    return "none"
