from __future__ import annotations

import aiosqlite


async def init_self_heal_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS self_heal_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                proposed_fix TEXT NOT NULL,
                tests TEXT DEFAULT '',
                status TEXT DEFAULT 'proposal',
                task_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS self_heal_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER,
                status TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def create_self_heal_report(
    db_path: str,
    *,
    issue: str,
    diagnosis: str,
    proposed_fix: str,
    tests: str,
    task_id: int | None = None,
) -> int:
    await init_self_heal_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO self_heal_reports (issue, diagnosis, proposed_fix, tests, task_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (issue, diagnosis, proposed_fix, tests, task_id),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def latest_self_heal_report(db_path: str) -> dict[str, str | int] | None:
    await init_self_heal_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM self_heal_reports
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def record_self_heal_stage(db_path: str, report_id: int | None, status: str, details: str) -> None:
    await init_self_heal_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO self_heal_stages (report_id, status, details) VALUES (?, ?, ?)",
            (report_id, status, details[:1000]),
        )
        await db.commit()


async def latest_self_heal_stages(db_path: str, limit: int = 8, report_id: int | None = None) -> list[dict[str, str | int]]:
    await init_self_heal_db(db_path)
    where = "WHERE report_id = ?" if report_id is not None else ""
    params = (report_id, limit) if report_id is not None else (limit,)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT report_id, status, details, created_at
            FROM self_heal_stages
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in reversed(rows)]
