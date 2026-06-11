from __future__ import annotations

import re

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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS qa_disagreement_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_type TEXT NOT NULL,
                topic TEXT NOT NULL,
                artifact_path TEXT NOT NULL DEFAULT '',
                rule_id TEXT NOT NULL,
                rule_class TEXT NOT NULL,
                severity TEXT NOT NULL,
                validator_verdict TEXT NOT NULL,
                reviewer_verdict TEXT NOT NULL,
                arbiter_verdict TEXT NOT NULL DEFAULT '',
                attempt_number INTEGER NOT NULL DEFAULT 1,
                final_action TEXT NOT NULL,
                evidence TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                resolved_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor = await db.execute("PRAGMA table_info(qa_disagreement_events)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "status" not in columns:
            await db.execute("ALTER TABLE qa_disagreement_events ADD COLUMN status TEXT NOT NULL DEFAULT 'open'")
        if "resolved_at" not in columns:
            await db.execute("ALTER TABLE qa_disagreement_events ADD COLUMN resolved_at DATETIME")
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


async def record_qa_disagreement(
    db_path: str,
    *,
    artifact_type: str,
    topic: str,
    artifact_path: str = "",
    rule_id: str,
    rule_class: str,
    severity: str,
    validator_verdict: str,
    reviewer_verdict: str,
    arbiter_verdict: str = "",
    attempt_number: int = 1,
    final_action: str,
    evidence: str = "",
) -> None:
    await init_artifact_review_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO qa_disagreement_events (
                artifact_type, topic, artifact_path, rule_id, rule_class, severity,
                validator_verdict, reviewer_verdict, arbiter_verdict, attempt_number,
                final_action, evidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_type,
                topic,
                artifact_path,
                rule_id,
                rule_class,
                severity,
                validator_verdict,
                reviewer_verdict,
                arbiter_verdict,
                max(1, attempt_number),
                final_action,
                evidence.strip()[:3000],
            ),
        )
        await db.commit()


async def qa_disagreement_summary_text(db_path: str, *, days: int = 7) -> str:
    await init_artifact_review_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                count(*) AS total,
                sum(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS resolved,
                sum(CASE WHEN status != 'resolved' THEN 1 ELSE 0 END) AS open
            FROM qa_disagreement_events
            WHERE created_at >= datetime('now', ?)
            """,
            (f"-{max(1, days)} days",),
        )
        total_row = await cursor.fetchone()
        total = int(total_row["total"] or 0) if total_row else 0
        if total == 0:
            return f"QA disagreements in the last {days} days: 0."
        resolved = int(total_row["resolved"] or 0)
        open_count = int(total_row["open"] or 0)
        cursor = await db.execute(
            """
            SELECT rule_id, count(*) AS count
            FROM qa_disagreement_events
            WHERE created_at >= datetime('now', ?)
            GROUP BY rule_id
            ORDER BY count DESC, rule_id ASC
            LIMIT 3
            """,
            (f"-{max(1, days)} days",),
        )
        rows = await cursor.fetchall()
    top = ", ".join(f"{row['rule_id']} x{row['count']}" for row in rows)
    return f"QA disagreements in the last {days} days: {total} ({open_count} open, {resolved} resolved). Top suspect rules: {top}."


async def weekly_artifact_review_text(db_path: str, *, days: int = 7) -> str:
    await init_artifact_review_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT artifact_type, topic, reviewer_model, passed, review_text, created_at
            FROM artifact_reviews
            WHERE created_at >= datetime('now', ?)
            ORDER BY id DESC
            LIMIT 10
            """,
            (f"-{max(1, days)} days",),
        )
        reviews = await cursor.fetchall()
        cursor = await db.execute(
            """
            SELECT id, artifact_type, topic, rule_id, rule_class, severity, validator_verdict,
                   reviewer_verdict, arbiter_verdict, final_action, evidence, status, created_at
            FROM qa_disagreement_events
            WHERE created_at >= datetime('now', ?)
            ORDER BY id DESC
            LIMIT 20
            """,
            (f"-{max(1, days)} days",),
        )
        disagreements = await cursor.fetchall()
    lines = [f"Artifact review activity for the last {days} days:"]
    if reviews:
        lines.append("\nSemantic reviews:")
        for index, row in enumerate(reviews, 1):
            status = "PASS" if row["passed"] else "REJECT"
            summary = " ".join(str(row["review_text"]).split())[:180]
            lines.append(f"{index}. {status} {row['artifact_type']} — {row['topic']} ({row['reviewer_model']}, {row['created_at']})")
            if summary:
                lines.append(f"   {summary}")
    else:
        lines.append("\nSemantic reviews: none.")
    if disagreements:
        lines.append("\nQA disagreements:")
        for index, row in enumerate(disagreements, 1):
            base = (
                f"{index}. #{row['id']} {row['status'].upper()} {row['rule_id']} "
                f"({row['rule_class']}/{row['severity']}) — {row['topic']} -> {row['final_action']}"
            )
            if row["status"] == "resolved":
                base = f"~~{base}~~"
            lines.append(base)
            verdicts = f"   validator={row['validator_verdict']}; reviewer={row['reviewer_verdict']}"
            if row["arbiter_verdict"]:
                verdicts += f"; arbiter={row['arbiter_verdict']}"
            lines.append(verdicts)
    else:
        lines.append("\nQA disagreements: none.")
    return "\n".join(lines)


async def resolve_review_activity_text(db_path: str, text: str, *, days: int = 7) -> str | None:
    lowered = text.lower().strip()
    if not any(word in lowered for word in ("resolved", "resolve", "fixed", "close", "closed")):
        return None
    if "review" not in lowered and "qa" not in lowered and "validator" not in lowered:
        return None
    match = re.search(r"(?:#|number\s+|item\s+|review\s+|qa\s+)?(\d+)", lowered)
    if not match:
        return "Tell me the review number to resolve, for example: review 2 is resolved."
    number = int(match.group(1))
    await init_artifact_review_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, rule_id, topic
            FROM qa_disagreement_events
            WHERE created_at >= datetime('now', ?)
            ORDER BY id DESC
            LIMIT 20
            """,
            (f"-{max(1, days)} days",),
        )
        rows = await cursor.fetchall()
        if not rows:
            return "There are no QA disagreement review items to resolve this week."
        if number < 1 or number > len(rows):
            return f"I can only resolve review numbers 1 to {len(rows)} from this week's QA list."
        row = rows[number - 1]
        await db.execute(
            """
            UPDATE qa_disagreement_events
            SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (row["id"],),
        )
        await db.commit()
    return f"Marked review {number} as resolved: {row['rule_id']} for {row['topic']}."


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
        weekly = await weekly_artifact_review_text(db_path)
        return f"No artifact review has been stored yet.\n\n{weekly}"
    status = "PASS" if row["passed"] else "REJECT"
    weekly = await weekly_artifact_review_text(db_path)
    return (
        "Last artifact review:\n"
        f"1) artifact: {row['artifact_type']}\n"
        f"2) topic: {row['topic']}\n"
        f"3) reviewer: {row['reviewer_model']}\n"
        f"4) status: {status}\n"
        f"5) time: {row['created_at']}\n"
        f"6) review:\n{row['review_text']}\n\n"
        f"{weekly}"
    )
