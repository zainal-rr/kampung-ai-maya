from __future__ import annotations

from canonical_memory import forget_canonical_memory, upsert_canonical_memory
from memory_links import add_memory_link

ASSOCIATION_RECALL3_FLOOR = 1.0


async def seed_association_memories(db_path: str) -> None:
    sink_id = await upsert_canonical_memory(
        db_path,
        raw_text="Ahmad fixed my sink",
        content="Ahmad fixed my sink",
        kind="profile_fact",
        scope="global",
        source_channel="recall_eval",
        confidence="high",
    )
    phone_id = await upsert_canonical_memory(
        db_path,
        raw_text="Ahmad phone number is 017-555",
        content="Ahmad phone number is 017-555",
        kind="profile_fact",
        scope="global",
        source_channel="recall_eval",
        confidence="high",
    )
    ok = await add_memory_link(db_path, sink_id, phone_id, relation="shared_entity", source_channel="recall_eval")
    if not ok:
        raise AssertionError("failed to seed active association link")

    laptop_id = await upsert_canonical_memory(
        db_path,
        raw_text="Mariam repaired my laptop",
        content="Mariam repaired my laptop",
        kind="profile_fact",
        scope="global",
        source_channel="recall_eval",
        confidence="high",
    )
    fabric_id = await upsert_canonical_memory(
        db_path,
        raw_text="Mariam curtain fabric is violet",
        content="Mariam curtain fabric is violet",
        kind="profile_fact",
        scope="global",
        source_channel="recall_eval",
        confidence="high",
    )
    ok = await add_memory_link(db_path, laptop_id, fabric_id, relation="shared_entity", source_channel="recall_eval")
    if not ok:
        raise AssertionError("failed to seed forgotten-neighbor association link")
    await forget_canonical_memory(db_path, "Mariam curtain fabric")


def association_metrics(results: list[dict[str, object]]) -> dict[str, float | int]:
    rows = [item for item in results if item["category"] == "association"]
    expected = [item for item in rows if "expect" in item]
    return {
        "cases": len(rows),
        "recall_at_3": round(sum(bool(item["hit_at_3"]) for item in expected) / len(expected), 3)
        if expected else 0,
        "direct_leaks": sum(bool(item.get("direct_leaked")) for item in rows),
        "forgotten_neighbor_leaks": sum(bool(item.get("leaked")) for item in rows),
    }


def association_failures(metrics: dict[str, dict[str, float | int]]) -> list[str]:
    values = metrics.get("association", {})
    failures = []
    if float(values.get("recall_at_3", 0)) < ASSOCIATION_RECALL3_FLOOR:
        failures.append(f"association recall@3 {values.get('recall_at_3')} below floor {ASSOCIATION_RECALL3_FLOOR}")
    if int(values.get("direct_leaks", 0)):
        failures.append("association neighbor leaked into direct recall")
    if int(values.get("forgotten_neighbor_leaks", 0)):
        failures.append("forgotten association neighbor leaked")
    return failures
