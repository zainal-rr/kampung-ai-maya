from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


"""Memory recall eval suite.

Measures what the retrieval layer actually does, per category, against a
seeded temp DB. Run: ./venv/bin/python memory_recall_eval.py

Hard-fail conditions (exit 1):
  - forgotten facts leak into recall (must be 0)
  - absent facts produce direct-fact answers (false recall, must be 0)
  - association links fail to enrich relevance context or leak into direct recall
  - exact-query recall@3 below 0.8
  - forget over-deletion or under-deletion scenario failures

Report-only categories: paraphrase, malay_manglish, voice_noisy, temporal_old.

Embeddings trigger (decided in advance so the decision is not vibes):
  add embeddings only if paraphrase recall@3 < 0.6 or malay_manglish
  recall@3 < 0.5 while exact recall@3 >= 0.9. Until then, FTS5 + token
  overlap is the retrieval stack.
"""

import asyncio
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import aiosqlite

from maya_memory.canonical_memory import (
    forget_canonical_memory,
    search_relevant_canonical_memories,
    upsert_canonical_memory,
)
from maya_core.learning_pipeline import LearningPipeline
from maya_core.lesson_store import init_lesson_db
from maya_memory.memory_control import forget_memory
from maya_memory.memory_recall_eval_cases import CASES, SEED_FACTS
from maya_memory.memory_recall_eval_associations import association_failures, association_metrics, seed_association_memories
from maya_memory.memory_service import MemoryService
from maya_core.storage import init_db

EXACT_RECALL3_FLOOR = 0.8
EMBEDDINGS_TRIGGER = {"paraphrase_floor": 0.6, "malay_floor": 0.5, "exact_gate": 0.9}


async def run_eval() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="maya-memory-eval-") as tmp:
        db_path = str(Path(tmp) / "eval.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await _seed(db_path)
        await seed_association_memories(db_path)
        results = [await _run_case(db_path, case) for case in CASES]
        scenarios = await _forget_scenarios(db_path)
        supersede = await _supersede_scenarios(db_path)
    metrics = _metrics(results)
    failures = _hard_failures(metrics, results, scenarios, supersede)
    trigger = _embeddings_trigger(metrics)
    return {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cases": len(results),
        "metrics": metrics,
        "forget_scenarios": scenarios,
        "supersede_scenarios": supersede,
        "hard_failures": failures,
        "embeddings_trigger": trigger,
        "results": results,
    }


async def _seed(db_path: str) -> None:
    for fact in SEED_FACTS:
        await upsert_canonical_memory(
            db_path,
            raw_text=fact["content"],
            content=fact["content"],
            kind=fact.get("kind", "preference"),
            scope=fact.get("scope", "global"),
            source_channel="recall_eval",
            confidence="high",
            pinned=bool(fact.get("pinned")),
        )
        if fact.get("forget"):
            await forget_canonical_memory(db_path, fact["content"])
        if fact.get("old_days"):
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "UPDATE canonical_memory_items SET updated_at = datetime('now', ?) WHERE content = ?",
                    (f"-{int(fact['old_days'])} days", fact["content"]),
                )
                await db.commit()
        if fact.get("expire"):
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    """
                    UPDATE canonical_memory_items
                    SET status = 'expired',
                        expires_at = datetime('now', '-1 day'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE content = ?
                    """,
                    (fact["content"],),
                )
                await db.commit()


async def _run_case(db_path: str, case: dict[str, str]) -> dict[str, object]:
    query = case["query"]
    started = time.perf_counter()
    relevant = await search_relevant_canonical_memories(db_path, query, limit=3)
    direct = await MemoryService(db_path).search_direct_fact(query, limit=3)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    top1 = ([*direct[:1], *relevant[:1]])
    pool = [*direct, *relevant]
    record: dict[str, object] = {
        "category": case["category"],
        "query": query,
        "direct": direct,
        "relevant": relevant,
        "elapsed_ms": elapsed_ms,
    }
    if "expect" in case:
        needle = case["expect"].casefold()
        record["expect"] = case["expect"]
        record["hit_at_1"] = any(needle in item.casefold() for item in top1)
        record["hit_at_3"] = any(needle in item.casefold() for item in pool)
        direct_needle = str(case.get("direct_forbid", "")).casefold()
        record["direct_leaked"] = bool(direct_needle) and any(direct_needle in item.casefold() for item in direct)
        forbid_needle = str(case.get("forbid", "")).casefold()
        record["leaked"] = bool(forbid_needle) and any(forbid_needle in item.casefold() for item in pool)
    elif "forbid" in case:
        needle = case["forbid"].casefold()
        record["forbid"] = case["forbid"]
        record["leaked"] = any(needle in item.casefold() for item in pool)
    else:
        record["false_direct_recall"] = bool(direct)
    return record


async def _forget_scenarios(db_path: str) -> list[dict[str, object]]:
    scenarios: list[dict[str, object]] = []
    # Scenario 1: canonical-only. Forget A; sibling B sharing a token survives.
    for content in ("my badminton night is Friday", "my badminton racket brand is Yonex"):
        await upsert_canonical_memory(
            db_path, raw_text=content, content=content, kind="preference",
            scope="global", source_channel="recall_eval", confidence="high",
        )
    await forget_memory(db_path, "my badminton night")
    gone = await MemoryService(db_path).search_direct_fact("what is my badminton night")
    kept = await MemoryService(db_path).search_direct_fact("what is my badminton racket brand")
    scenarios.append({
        "name": "canonical forget",
        "under_deletion_ok": not gone,
        "over_deletion_ok": any("Yonex" in item for item in kept),
    })
    # Scenario 2: cross-store via the real save pipeline (preference + lesson
    # + canonical), then forget through the registry.
    pipeline = LearningPipeline(db_path, extraction_agent=None)
    await pipeline.handle("remember that my parking level is B2", "telegram")
    await pipeline.handle("remember that my parking sticker colour is green", "telegram")
    await forget_memory(db_path, "my parking level")
    gone = await MemoryService(db_path).search_direct_fact("what is my parking level")
    kept = await MemoryService(db_path).search_direct_fact("what is my parking sticker colour")
    scenarios.append({
        "name": "cross-store forget",
        "under_deletion_ok": not gone,
        "over_deletion_ok": any("green" in item for item in kept),
    })
    return scenarios


async def _supersede_scenarios(db_path: str) -> list[dict[str, object]]:
    scenarios: list[dict[str, object]] = []
    await upsert_canonical_memory(
        db_path,
        raw_text="remember that I prefer short replies",
        content="I prefer short replies",
        kind="preference",
        scope="global",
        source_channel="recall_eval",
        confidence="high",
    )
    await upsert_canonical_memory(
        db_path,
        raw_text="actually I prefer detailed replies",
        content="I prefer detailed replies",
        kind="preference",
        scope="global",
        source_channel="recall_eval",
        confidence="high",
    )
    direct = await MemoryService(db_path).search_direct_fact("what is my reply style", limit=3)
    relevant = await search_relevant_canonical_memories(db_path, "how should Maya answer me", limit=3)
    pool = [*(direct or []), *relevant]
    scenarios.append({
        "name": "reply preference supersede",
        "newer_value_ok": any("detailed" in item.casefold() for item in pool[:3]),
        "old_value_not_current": not any("short replies" in item.casefold() for item in (direct or [])[:1]),
        "direct": direct or [],
        "relevant": relevant,
    })
    return scenarios


def _metrics(results: list[dict[str, object]]) -> dict[str, dict[str, float | int]]:
    metrics: dict[str, dict[str, float | int]] = {}
    for category in ("exact", "paraphrase", "malay_manglish", "voice_noisy", "temporal_old", "conflict"):
        rows = [item for item in results if item["category"] == category]
        if not rows:
            continue
        metrics[category] = {
            "cases": len(rows),
            "hits_at_1": sum(bool(item["hit_at_1"]) for item in rows),
            "hits_at_3": sum(bool(item["hit_at_3"]) for item in rows),
            "recall_at_1": round(sum(bool(item["hit_at_1"]) for item in rows) / len(rows), 3),
            "recall_at_3": round(sum(bool(item["hit_at_3"]) for item in rows) / len(rows), 3),
            "leaks": sum(bool(item.get("leaked")) for item in rows),
            "direct_leaks": sum(bool(item.get("direct_leaked")) for item in rows),
        }
    metrics["association"] = association_metrics(results)
    forgotten = [item for item in results if item["category"] == "forgotten"]
    excluded = [item for item in results if item["category"] == "excluded"]
    absent = [item for item in results if item["category"] == "absent"]
    metrics["forgotten"] = {"cases": len(forgotten), "leaks": sum(bool(item["leaked"]) for item in forgotten)}
    metrics["excluded"] = {"cases": len(excluded), "leaks": sum(bool(item["leaked"]) for item in excluded)}
    metrics["absent"] = {"cases": len(absent), "false_direct_recalls": sum(bool(item["false_direct_recall"]) for item in absent)}
    return metrics


def _hard_failures(
    metrics: dict[str, dict[str, float | int]],
    results: list[dict[str, object]],
    scenarios: list[dict[str, object]],
    supersede_scenarios: list[dict[str, object]],
) -> list[str]:
    failures: list[str] = []
    if metrics["forgotten"]["leaks"]:
        leaked = [item["query"] for item in results if item.get("leaked")]
        failures.append(f"forgotten facts leaked: {leaked}")
    if metrics["excluded"]["leaks"]:
        leaked = [item["query"] for item in results if item["category"] == "excluded" and item.get("leaked")]
        failures.append(f"excluded old/expired facts leaked: {leaked}")
    if metrics["absent"]["false_direct_recalls"]:
        false = [item["query"] for item in results if item.get("false_direct_recall")]
        failures.append(f"false direct recall on absent facts: {false}")
    for category in ("exact", "paraphrase", "malay_manglish", "voice_noisy", "temporal_old", "conflict"):
        leaked = [item["query"] for item in results if item["category"] == category and item.get("leaked")]
        if leaked:
            failures.append(f"{category} cases leaked forbidden values: {leaked}")
        direct_leaked = [item["query"] for item in results if item["category"] == category and item.get("direct_leaked")]
        if direct_leaked:
            failures.append(f"{category} cases leaked direct-forbidden values: {direct_leaked}")
    exact = metrics.get("exact", {})
    if float(exact.get("recall_at_3", 0)) < EXACT_RECALL3_FLOOR:
        failures.append(f"exact recall@3 {exact.get('recall_at_3')} below floor {EXACT_RECALL3_FLOOR}")
    failures.extend(association_failures(metrics))
    for scenario in scenarios:
        if not scenario["under_deletion_ok"]:
            failures.append(f"{scenario['name']}: forgotten fact still recallable (under-deletion)")
        if not scenario["over_deletion_ok"]:
            failures.append(f"{scenario['name']}: sibling fact lost (over-deletion)")
    for scenario in supersede_scenarios:
        if not scenario["newer_value_ok"]:
            failures.append(f"{scenario['name']}: newer corrected fact not recallable")
        if not scenario["old_value_not_current"]:
            failures.append(f"{scenario['name']}: old superseded fact still won direct recall")
    return failures


def _embeddings_trigger(metrics: dict[str, dict[str, float | int]]) -> dict[str, object]:
    exact = float(metrics.get("exact", {}).get("recall_at_3", 0))
    paraphrase = float(metrics.get("paraphrase", {}).get("recall_at_3", 0))
    malay = float(metrics.get("malay_manglish", {}).get("recall_at_3", 0))
    gated = exact >= EMBEDDINGS_TRIGGER["exact_gate"]
    fired = gated and (
        paraphrase < EMBEDDINGS_TRIGGER["paraphrase_floor"]
        or malay < EMBEDDINGS_TRIGGER["malay_floor"]
    )
    return {
        "fired": fired,
        "reason": (
            f"exact@3={exact}, paraphrase@3={paraphrase}, malay@3={malay}; "
            f"trigger: paraphrase<{EMBEDDINGS_TRIGGER['paraphrase_floor']} or "
            f"malay<{EMBEDDINGS_TRIGGER['malay_floor']} while exact>={EMBEDDINGS_TRIGGER['exact_gate']}"
        ),
    }


def _report_path() -> Path:
    out_dir = _ROOT / "logs" / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return out_dir / f"memory_recall_eval-{stamp}.json"


async def _main() -> int:
    report = await run_eval()
    path = _report_path()
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Memory recall eval ({report['cases']} cases + {len(report['forget_scenarios'])} forget scenarios)")
    for category, values in report["metrics"].items():
        print(f"  {category}: {values}")
    for scenario in report["forget_scenarios"]:
        print(f"  {scenario['name']}: under_deletion_ok={scenario['under_deletion_ok']}, over_deletion_ok={scenario['over_deletion_ok']}")
    for scenario in report["supersede_scenarios"]:
        print(f"  {scenario['name']}: newer_value_ok={scenario['newer_value_ok']}, old_value_not_current={scenario['old_value_not_current']}")
    trigger = report["embeddings_trigger"]
    print(f"  embeddings trigger fired: {trigger['fired']} ({trigger['reason']})")
    print(f"  report: {path}")
    if report["hard_failures"]:
        print("HARD FAILURES:")
        for failure in report["hard_failures"]:
            print(f"  - {failure}")
        return 1
    print("memory_recall_eval: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
