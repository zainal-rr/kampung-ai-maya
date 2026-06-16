from __future__ import annotations

import re

import aiosqlite

from permission_policy import contains_sensitive_info

MAYA_CORE_CAP = 2477
ZAINAL_PROFILE_CAP = 1499
CORE_SCOPE = "maya_core_memory"
PROFILE_SCOPE = "zainal_profile_summary"


async def init_curated_memory_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS curated_memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT 'explicit',
                confidence REAL DEFAULT 0.86,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def add_curated_memory(
    db_path: str,
    content: str,
    *,
    scope: str | None = None,
    source: str = "explicit",
) -> tuple[bool, str]:
    await init_curated_memory_db(db_path)
    cleaned = _clean_entry(content)
    if not cleaned:
        return False, "I need a clearer memory before saving it."
    if contains_sensitive_info(cleaned):
        return False, "I cannot save that because it looks sensitive."
    target = scope or classify_memory(cleaned)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, content FROM curated_memory_items
            WHERE scope = ? AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            """,
            (target,),
        )
        rows = await cursor.fetchall()
        existing = [str(row["content"]) for row in rows]
        if _duplicate(cleaned, existing):
            return True, "That memory is already saved."
        await db.execute(
            """
            INSERT INTO curated_memory_items (scope, content, source, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (target, cleaned[:1000], source[:120]),
        )
        await db.commit()
    await consolidate_scope(db_path, target)
    return True, f"Saved to {target}."


async def curated_memory_prompt(db_path: str) -> str:
    core = await scope_summary(db_path, CORE_SCOPE)
    profile = await scope_summary(db_path, PROFILE_SCOPE)
    blocks = []
    if core["summary"]:
        blocks.append(_prompt_block("Maya core memory", core))
    if profile["summary"]:
        blocks.append(_prompt_block("Zainal profile summary", profile))
    return "\n\n".join(blocks)


async def curated_memory_status(db_path: str) -> str:
    core = await scope_summary(db_path, CORE_SCOPE)
    profile = await scope_summary(db_path, PROFILE_SCOPE)
    return "\n".join(
        [
            "Curated memory:",
            _status_line("maya_core_memory", core),
            _status_line("zainal_profile_summary", profile),
        ]
    )


async def scope_summary(db_path: str, scope: str) -> dict[str, str | int]:
    await init_curated_memory_db(db_path)
    cap = _cap(scope)
    items = await _active_items(db_path, scope)
    summary = "\n".join(items)
    return {
        "scope": scope,
        "summary": summary[:cap],
        "chars": min(len(summary), cap),
        "cap": cap,
        "percent": round(min(len(summary), cap) / cap * 100) if cap else 0,
        "count": len(items),
    }


async def consolidate_scope(db_path: str, scope: str) -> None:
    cap = _cap(scope)
    items = await _active_rows(db_path, scope)
    total = sum(len(str(item["content"])) + 1 for item in items)
    if total <= cap:
        return
    kept: list[str] = []
    used = 0
    for item in items:
        content = str(item["content"])
        size = len(content) + 1
        if used + size > cap:
            continue
        kept.append(content)
        used += size
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE curated_memory_items SET status = 'stale' WHERE scope = ?", (scope,))
        for content in kept:
            await db.execute(
                """
                INSERT INTO curated_memory_items (scope, content, source, updated_at)
                VALUES (?, ?, 'consolidated', CURRENT_TIMESTAMP)
                """,
                (scope, content),
            )
        await db.commit()


async def forget_curated_memory(db_path: str, query: str) -> int:
    await init_curated_memory_db(db_path)
    cleaned = query.strip()
    async with aiosqlite.connect(db_path) as db:
        if cleaned in (CORE_SCOPE, PROFILE_SCOPE):
            # Full-scope wipe only when the exact scope name is given.
            # A fuzzy `scope LIKE` here used to wipe a whole scope for any
            # query containing e.g. "maya" or "zainal".
            result = await db.execute(
                "DELETE FROM curated_memory_items WHERE scope = ?",
                (cleaned,),
            )
        else:
            result = await db.execute(
                "DELETE FROM curated_memory_items WHERE content LIKE ?",
                (f"%{cleaned}%",),
            )
        await db.commit()
    return result.rowcount


def classify_memory(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("i prefer", "my preference", "zainal", "telegram style", "reply", "anxious")):
        return PROFILE_SCOPE
    if any(word in lowered for word in ("kampung ai", "maya", "imac", "option space", "screen", "voice")):
        return CORE_SCOPE
    return PROFILE_SCOPE


async def _active_items(db_path: str, scope: str) -> list[str]:
    rows = await _active_rows(db_path, scope)
    return [str(row["content"]) for row in rows]


async def _active_rows(db_path: str, scope: str) -> list[aiosqlite.Row]:
    await init_curated_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, content FROM curated_memory_items
            WHERE scope = ? AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            """,
            (scope,),
        )
        return await cursor.fetchall()


def _prompt_block(title: str, data: dict[str, str | int]) -> str:
    return (
        f"{title} [{data['percent']} percent, {data['chars']}/{data['cap']} chars]\n"
        f"{data['summary']}"
    )


def _status_line(label: str, data: dict[str, str | int]) -> str:
    return f"1) {label}: {data['percent']} percent used, {data['chars']}/{data['cap']} chars, {data['count']} entries"


def _cap(scope: str) -> int:
    return MAYA_CORE_CAP if scope == CORE_SCOPE else ZAINAL_PROFILE_CAP


def _clean_entry(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    cleaned = re.sub(r"^(?:remember that|remember|save this memory[: ]*)", "", cleaned, flags=re.I).strip()
    return cleaned


def _duplicate(text: str, existing: list[str]) -> bool:
    normalized = text.casefold()
    return any(normalized == item.casefold() for item in existing)
