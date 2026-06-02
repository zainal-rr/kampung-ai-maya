from __future__ import annotations

import aiosqlite


async def init_artifact_review_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS artifact_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_type TEXT NOT NULL,
                topic TEXT NOT NULL,
                reviewer_model TEXT NOT NULL,
                passed INTEGER NOT NULL,
                review_text TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def record_artifact_review(
    db_path: str,
    artifact_type: str,
    topic: str,
    reviewer_model: str,
    passed: bool,
    review_text: str,
) -> None:
    await init_artifact_review_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO artifact_reviews (artifact_type, topic, reviewer_model, passed, review_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (artifact_type, topic, reviewer_model, 1 if passed else 0, review_text.strip()[:6000]),
        )
        await db.commit()


async def latest_artifact_review_text(db_path: str) -> str:
    await init_artifact_review_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT artifact_type, topic, reviewer_model, passed, review_text, created_at
            FROM artifact_reviews
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    if not row:
        return "No artifact review has been stored yet."
    status = "PASS" if row["passed"] else "REJECT"
    return (
        "Last artifact review:\n"
        f"1) artifact: {row['artifact_type']}\n"
        f"2) topic: {row['topic']}\n"
        f"3) reviewer: {row['reviewer_model']}\n"
        f"4) status: {status}\n"
        f"5) time: {row['created_at']}\n"
        f"6) review:\n{row['review_text']}"
    )
