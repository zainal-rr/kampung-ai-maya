from __future__ import annotations

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
    return (
        "Last route:\n"
        f"1) input: {row['input_type']}\n"
        f"2) lane: {row['lane']}\n"
        f"3) reason: {row['reason']}\n"
        f"4) cost recorded: {cost}\n"
        f"5) time: {row['created_at']}"
    )
