from __future__ import annotations

import aiosqlite


async def relevant_items_for_selected(
    db_path: str,
    selected: list[tuple[int, str, str]],
) -> list[dict[str, object]]:
    item_by_id: dict[str, dict[str, object]] = {}
    if selected:
        placeholders = ",".join("?" for _score, _memory_id, _content in selected)
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"""
                SELECT memory_id, content, provenance_json, untrusted_influence, injection_detected
                FROM canonical_memory_items
                WHERE memory_id IN ({placeholders})
                """,
                tuple(memory_id for _score, memory_id, _content in selected),
            )
            for row in await cursor.fetchall():
                item_by_id[str(row["memory_id"])] = {
                    "memory_id": str(row["memory_id"]),
                    "content": str(row["content"]),
                    "provenance_json": str(row["provenance_json"] or "{}"),
                    "untrusted_influence": bool(row["untrusted_influence"]),
                    "injection_detected": bool(row["injection_detected"]),
                }
    return [
        item_by_id.get(memory_id, {
            "memory_id": memory_id,
            "content": content,
            "provenance_json": "{}",
            "untrusted_influence": True,
            "injection_detected": False,
        })
        for _score, memory_id, content in selected
    ]
