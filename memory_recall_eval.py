from __future__ import annotations

"""Memory recall eval suite.

Measures what the retrieval layer actually does, per category, against a
seeded temp DB. Run: ./venv/bin/python memory_recall_eval.py

Hard-fail conditions (exit 1):
  - forgotten facts leak into recall (must be 0)
  - absent facts produce direct-fact answers (false recall, must be 0)
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
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from canonical_memory import (
    forget_canonical_memory,
    search_relevant_canonical_memories,
    upsert_canonical_memory,
)
from learning_pipeline import LearningPipeline
from lesson_store import init_lesson_db
from memory_control import forget_memory
from memory_service import MemoryService
from storage import init_db

EXACT_RECALL3_FLOOR = 0.8
EMBEDDINGS_TRIGGER = {"paraphrase_floor": 0.6, "malay_floor": 0.5, "exact_gate": 0.9}

SEED_FACTS = (
    {"content": "my favourite snack is kuih lapis"},
    {"content": "my favourite drink is teh ais"},
    {"content": "my home wifi network name is KampungNet"},
    {"content": "Zainal works night shifts on weekends"},
    {"content": "my preferred reply style is short and direct"},
    {"content": "saya suka makan nasi lemak waktu pagi"},
    {"content": "my favourite kopitiam in Bandar is Kedai Kopi Seng"},
    {"content": "my car is a grey Toyota Hilux"},
    {"content": "my gym day is every Tuesday and Thursday"},
    {"content": "kampung ai dashboard port is 8787", "kind": "project_fact", "scope": "project:kampung-ai"},
    {"content": "my favourite fruit is durian"},
    {"content": "Maya must always reply concisely on Telegram", "pinned": True},
    {"content": "my driving licence renewal is in March", "old_days": 200},
    {"content": "my favourite colour is purple", "forget": True},
    {"content": "my lunch budget is 15 dollars", "forget": True},
)

CASES = (
    # exact: near-literal restatements; the floor that must always hold.
    {"category": "exact", "query": "what is my favourite snack", "expect": "kuih lapis"},
    {"category": "exact", "query": "what is my favourite drink", "expect": "teh ais"},
    {"category": "exact", "query": "my home wifi network name", "expect": "KampungNet"},
    {"category": "exact", "query": "what is my preferred reply style", "expect": "short and direct"},
    {"category": "exact", "query": "what is my gym day", "expect": "Tuesday"},
    {"category": "exact", "query": "kampung ai dashboard port", "expect": "8787"},
    {"category": "exact", "query": "what is my favourite fruit", "expect": "durian"},
    {"category": "exact", "query": "what is my car", "expect": "Hilux"},
    {"category": "exact", "query": "my favourite kopitiam in Bandar", "expect": "Kedai Kopi Seng"},
    {"category": "exact", "query": "does Zainal work night shifts", "expect": "weekends"},
    # paraphrase: same fact, different words. The known lexical-retrieval gap.
    {"category": "paraphrase", "query": "what food do I like to munch on", "expect": "kuih lapis"},
    {"category": "paraphrase", "query": "which drink do I usually order", "expect": "teh ais"},
    {"category": "paraphrase", "query": "do I work on weekends", "expect": "night shifts"},
    {"category": "paraphrase", "query": "how should you write your replies to me", "expect": "short and direct"},
    {"category": "paraphrase", "query": "which days do I exercise", "expect": "Tuesday"},
    {"category": "paraphrase", "query": "what vehicle do I own", "expect": "Hilux"},
    {"category": "paraphrase", "query": "name of my wifi at home", "expect": "KampungNet"},
    {"category": "paraphrase", "query": "which coffee shop do I like", "expect": "Kedai Kopi Seng"},
    {"category": "paraphrase", "query": "what should I eat for breakfast", "expect": "nasi lemak"},
    {"category": "paraphrase", "query": "when do I go to the gym", "expect": "Tuesday"},
    # malay_manglish: same-language and cross-language recall.
    {"category": "malay_manglish", "query": "apa makanan kegemaran saya waktu pagi", "expect": "nasi lemak"},
    {"category": "malay_manglish", "query": "saya suka makan apa", "expect": "nasi lemak"},
    {"category": "malay_manglish", "query": "apa minuman kegemaran saya", "expect": "teh ais"},
    {"category": "malay_manglish", "query": "snack kegemaran saya apa eh", "expect": "kuih lapis"},
    {"category": "malay_manglish", "query": "what I like makan in the morning ah", "expect": "nasi lemak"},
    {"category": "malay_manglish", "query": "kopitiam mana saya suka", "expect": "Kedai Kopi Seng"},
    {"category": "malay_manglish", "query": "kereta saya apa", "expect": "Hilux"},
    # voice_noisy: STT typos and dropped letters.
    {"category": "voice_noisy", "query": "what is my favrite snack", "expect": "kuih lapis"},
    {"category": "voice_noisy", "query": "wats my fav drink", "expect": "teh ais"},
    {"category": "voice_noisy", "query": "what is my home wifi network nam", "expect": "KampungNet"},
    {"category": "voice_noisy", "query": "what days i go gym ah", "expect": "Tuesday"},
    {"category": "voice_noisy", "query": "kampung ai dash board port", "expect": "8787"},
    {"category": "voice_noisy", "query": "what is my favourite froot", "expect": "durian"},
    # temporal_old: facts last touched 200 days ago must still recall.
    {"category": "temporal_old", "query": "when is my driving licence renewal", "expect": "March"},
    {"category": "temporal_old", "query": "my driving licence renewal", "expect": "March"},
    {"category": "temporal_old", "query": "how must you reply on telegram", "expect": "concisely"},
    # forgotten: explicitly forgotten facts must never surface.
    {"category": "forgotten", "query": "what is my favourite colour", "forbid": "purple"},
    {"category": "forgotten", "query": "my favourite colour", "forbid": "purple"},
    {"category": "forgotten", "query": "what is my lunch budget", "forbid": "15 dollars"},
    {"category": "forgotten", "query": "lunch budget", "forbid": "15 dollars"},
    # absent: never-saved facts; direct recall must stay empty.
    {"category": "absent", "query": "what is my blood type"},
    {"category": "absent", "query": "what is my shoe size"},
    {"category": "absent", "query": "what is my office parking spot"},
    {"category": "absent", "query": "where did I park the car yesterday"},
    {"category": "absent", "query": "what is my netflix password"},
    {"category": "absent", "query": "what is my favourite movie"},
)


async def run_eval() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="maya-memory-eval-") as tmp:
        db_path = str(Path(tmp) / "eval.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await _seed(db_path)
        results = [await _run_case(db_path, case) for case in CASES]
        scenarios = await _forget_scenarios(db_path)
    metrics = _metrics(results)
    failures = _hard_failures(metrics, results, scenarios)
    trigger = _embeddings_trigger(metrics)
    return {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cases": len(results),
        "metrics": metrics,
        "forget_scenarios": scenarios,
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


async def _run_case(db_path: str, case: dict[str, str]) -> dict[str, object]:
    query = case["query"]
    relevant = await search_relevant_canonical_memories(db_path, query, limit=3)
    direct = await MemoryService(db_path).search_direct_fact(query, limit=3)
    top1 = ([*direct[:1], *relevant[:1]])
    pool = [*direct, *relevant]
    record: dict[str, object] = {
        "category": case["category"],
        "query": query,
        "direct": direct,
        "relevant": relevant,
    }
    if "expect" in case:
        needle = case["expect"].casefold()
        record["expect"] = case["expect"]
        record["hit_at_1"] = any(needle in item.casefold() for item in top1)
        record["hit_at_3"] = any(needle in item.casefold() for item in pool)
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


def _metrics(results: list[dict[str, object]]) -> dict[str, dict[str, float | int]]:
    metrics: dict[str, dict[str, float | int]] = {}
    for category in ("exact", "paraphrase", "malay_manglish", "voice_noisy", "temporal_old"):
        rows = [item for item in results if item["category"] == category]
        if not rows:
            continue
        metrics[category] = {
            "cases": len(rows),
            "recall_at_1": round(sum(bool(item["hit_at_1"]) for item in rows) / len(rows), 3),
            "recall_at_3": round(sum(bool(item["hit_at_3"]) for item in rows) / len(rows), 3),
        }
    forgotten = [item for item in results if item["category"] == "forgotten"]
    absent = [item for item in results if item["category"] == "absent"]
    metrics["forgotten"] = {"cases": len(forgotten), "leaks": sum(bool(item["leaked"]) for item in forgotten)}
    metrics["absent"] = {"cases": len(absent), "false_direct_recalls": sum(bool(item["false_direct_recall"]) for item in absent)}
    return metrics


def _hard_failures(
    metrics: dict[str, dict[str, float | int]],
    results: list[dict[str, object]],
    scenarios: list[dict[str, object]],
) -> list[str]:
    failures: list[str] = []
    if metrics["forgotten"]["leaks"]:
        leaked = [item["query"] for item in results if item.get("leaked")]
        failures.append(f"forgotten facts leaked: {leaked}")
    if metrics["absent"]["false_direct_recalls"]:
        false = [item["query"] for item in results if item.get("false_direct_recall")]
        failures.append(f"false direct recall on absent facts: {false}")
    exact = metrics.get("exact", {})
    if float(exact.get("recall_at_3", 0)) < EXACT_RECALL3_FLOOR:
        failures.append(f"exact recall@3 {exact.get('recall_at_3')} below floor {EXACT_RECALL3_FLOOR}")
    for scenario in scenarios:
        if not scenario["under_deletion_ok"]:
            failures.append(f"{scenario['name']}: forgotten fact still recallable (under-deletion)")
        if not scenario["over_deletion_ok"]:
            failures.append(f"{scenario['name']}: sibling fact lost (over-deletion)")
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
    out_dir = Path(__file__).resolve().parent / "logs" / "evals"
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
