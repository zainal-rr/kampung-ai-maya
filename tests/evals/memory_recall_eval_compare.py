from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


"""Compare canonical-memory recall with and without embedding rerank."""

import asyncio
import math
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tests.evals.memory_recall_eval import run_eval

THRESHOLD_GRID = (10, 15, 20, 25, 30)
DELTA_RECALL_FLOOR = 0.10
DELTA_HIT_FLOOR = 3
WEAK_PATH_P95_BUDGET_MS = 1200.0
GAIN_CATEGORIES = ("paraphrase", "malay_manglish")
LATENCY_CATEGORIES = ("paraphrase", "malay_manglish", "conflict", "excluded", "absent")
MIN_COVERAGE = {
    "paraphrase_total": 20,
    "conflict": 10,
    "excluded": 10,
    "absent": 12,
}


async def _run_with_flag(flag: str, *, threshold: int | None = None) -> dict[str, object]:
    old_value = os.environ.get("MEMORY_EMBED_RERANK_LIVE")
    old_threshold = os.environ.get("MEMORY_DIRECT_SEMANTIC_WEAK_THRESHOLD")
    os.environ["MEMORY_EMBED_RERANK_LIVE"] = flag
    if threshold is not None:
        os.environ["MEMORY_DIRECT_SEMANTIC_WEAK_THRESHOLD"] = str(threshold)
    try:
        report = await run_eval()
    finally:
        if old_value is None:
            os.environ.pop("MEMORY_EMBED_RERANK_LIVE", None)
        else:
            os.environ["MEMORY_EMBED_RERANK_LIVE"] = old_value
        if old_threshold is None:
            os.environ.pop("MEMORY_DIRECT_SEMANTIC_WEAK_THRESHOLD", None)
        else:
            os.environ["MEMORY_DIRECT_SEMANTIC_WEAK_THRESHOLD"] = old_threshold
    report["rerank_flag"] = flag
    report["direct_semantic_weak_threshold"] = threshold
    return report


def _comparison(baseline: dict[str, object], rerank_reports: list[dict[str, object]]) -> dict[str, object]:
    base_metrics = baseline["metrics"]
    selected = _select_threshold_report(baseline, rerank_reports)
    rerank_metrics = selected["metrics"]
    categories = sorted(set(base_metrics) | set(rerank_metrics))
    rows = {}
    for category in categories:
        base = base_metrics.get(category, {})
        emb = rerank_metrics.get(category, {})
        rows[category] = {
            "baseline": base,
            "embedding": emb,
        }
    return {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modes_compared": (
            "lexical_neighbor_supersede",
            "lexical_neighbor_supersede_w2b_semantic_fallback",
        ),
        "baseline_hard_failures": baseline["hard_failures"],
        "embedding_hard_failures": selected["hard_failures"],
        "baseline_supersede": baseline.get("supersede_scenarios", []),
        "embedding_supersede": selected.get("supersede_scenarios", []),
        "threshold_grid": [report["direct_semantic_weak_threshold"] for report in rerank_reports],
        "selected_threshold": selected["direct_semantic_weak_threshold"],
        "threshold_is_provisional": True,
        "coverage": _coverage(base_metrics),
        "acceptance": _acceptance_details(baseline, selected),
        "metrics": rows,
        "recommendation": _recommendation(baseline, selected),
    }


def _recommendation(baseline: dict[str, object], rerank: dict[str, object]) -> str:
    acceptance = _acceptance_details(baseline, rerank)
    if not acceptance["coverage_ok"]:
        return "keep_w2b_off: eval coverage below W2-B acceptance bar"
    if rerank["hard_failures"]:
        return "keep_embedding_rerank_off: embedding run has hard failures"
    base = baseline["metrics"]
    emb = rerank["metrics"]
    if not acceptance["safety_ok"]:
        return "keep_embedding_rerank_off: leakage or false direct recall detected"
    if not acceptance["regression_ok"]:
        return "keep_embedding_rerank_off: exact/conflict regression detected"
    if not acceptance["recall_delta_ok"]:
        return "keep_embedding_rerank_off: no meaningful recall improvement"
    if not acceptance["latency_ok"]:
        return "keep_w2b_env_gated: recall improved but weak-path latency exceeds desk budget"
    return "candidate_for_default_provisional: meaningful gain, no safety regression, threshold is case-set-fitted"


def _select_threshold_report(baseline: dict[str, object], reports: list[dict[str, object]]) -> dict[str, object]:
    passing = [report for report in reports if _acceptance_details(baseline, report)["default_candidate"]]
    if passing:
        return sorted(passing, key=lambda item: int(item["direct_semantic_weak_threshold"] or 0))[0]
    return sorted(
        reports,
        key=lambda item: (
            _acceptance_details(baseline, item)["net_gain_hits"],
            -len(item["hard_failures"]),
            -int(item["direct_semantic_weak_threshold"] or 0),
        ),
        reverse=True,
    )[0]


def _acceptance_details(baseline: dict[str, object], rerank: dict[str, object]) -> dict[str, object]:
    base = baseline["metrics"]
    emb = rerank["metrics"]
    coverage = _coverage(base)
    base_hits, base_cases = _combined_hits(base, GAIN_CATEGORIES)
    emb_hits, emb_cases = _combined_hits(emb, GAIN_CATEGORIES)
    required_hit_delta = max(DELTA_HIT_FLOOR, math.ceil(base_cases * DELTA_RECALL_FLOOR))
    net_gain = emb_hits - base_hits
    safety_ok = (
        not emb.get("forgotten", {}).get("leaks")
        and not emb.get("excluded", {}).get("leaks")
        and not emb.get("absent", {}).get("false_direct_recalls")
        and not emb.get("conflict", {}).get("leaks")
        and not emb.get("conflict", {}).get("direct_leaks")
    )
    regression_ok = all(
        float(emb.get(category, {}).get("recall_at_3", 0))
        >= float(base.get(category, {}).get("recall_at_3", 0))
        for category in ("exact", "conflict")
    )
    p95 = _weak_path_added_latency_p95(baseline, rerank)
    recall_delta_ok = emb_cases == base_cases and net_gain >= required_hit_delta
    latency_ok = p95 <= WEAK_PATH_P95_BUDGET_MS
    coverage_ok = all(coverage[name]["ok"] for name in coverage)
    return {
        "coverage_ok": coverage_ok,
        "safety_ok": safety_ok,
        "regression_ok": regression_ok,
        "recall_delta_ok": recall_delta_ok,
        "latency_ok": latency_ok,
        "default_candidate": coverage_ok and safety_ok and regression_ok and recall_delta_ok and latency_ok and not rerank["hard_failures"],
        "base_gain_hits": base_hits,
        "embedding_gain_hits": emb_hits,
        "gain_cases": base_cases,
        "net_gain_hits": net_gain,
        "required_hit_delta": required_hit_delta,
        "weak_path_added_latency_p95_ms": p95,
        "latency_budget_ms": WEAK_PATH_P95_BUDGET_MS,
    }


def _coverage(metrics: dict[str, dict[str, float | int]]) -> dict[str, dict[str, object]]:
    paraphrase_total = int(metrics.get("paraphrase", {}).get("cases", 0)) + int(metrics.get("malay_manglish", {}).get("cases", 0))
    values = {
        "paraphrase_total": paraphrase_total,
        "conflict": int(metrics.get("conflict", {}).get("cases", 0)),
        "excluded": int(metrics.get("excluded", {}).get("cases", 0)),
        "absent": int(metrics.get("absent", {}).get("cases", 0)),
    }
    return {
        name: {"actual": actual, "required": MIN_COVERAGE[name], "ok": actual >= MIN_COVERAGE[name]}
        for name, actual in values.items()
    }


def _combined_hits(metrics: dict[str, dict[str, float | int]], categories: tuple[str, ...]) -> tuple[int, int]:
    hits = sum(int(metrics.get(category, {}).get("hits_at_3", 0)) for category in categories)
    cases = sum(int(metrics.get(category, {}).get("cases", 0)) for category in categories)
    return hits, cases


def _weak_path_added_latency_p95(baseline: dict[str, object], rerank: dict[str, object]) -> float:
    base_by_query = {str(item["query"]): item for item in baseline["results"]}
    deltas = []
    for item in rerank["results"]:
        if item["category"] not in LATENCY_CATEGORIES:
            continue
        base = base_by_query.get(str(item["query"]))
        if not base:
            continue
        deltas.append(max(0.0, float(item.get("elapsed_ms", 0)) - float(base.get("elapsed_ms", 0))))
    if not deltas:
        return 0.0
    deltas.sort()
    index = min(len(deltas) - 1, math.ceil(len(deltas) * 0.95) - 1)
    return round(deltas[index], 2)


def _report_path() -> Path:
    out_dir = _ROOT / "logs" / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return out_dir / f"memory_recall_eval_compare-{stamp}.json"


async def _main() -> int:
    baseline = await _run_with_flag("0")
    rerank_reports = [await _run_with_flag("1", threshold=threshold) for threshold in THRESHOLD_GRID]
    report = {
        "baseline": baseline,
        "embedding_rerank_grid": rerank_reports,
        "comparison": _comparison(baseline, rerank_reports),
    }
    path = _report_path()
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    comparison = report["comparison"]
    print(f"Memory recall compare ({baseline['cases']} cases)")
    print(f"  baseline hard failures: {len(comparison['baseline_hard_failures'])}")
    print(f"  embedding hard failures: {len(comparison['embedding_hard_failures'])}")
    print(f"  selected threshold: {comparison['selected_threshold']} (provisional/case-set-fitted)")
    print(f"  acceptance: {comparison['acceptance']}")
    for category, values in comparison["metrics"].items():
        print(f"  {category}: baseline={values['baseline']} embedding={values['embedding']}")
    print(f"  recommendation: {comparison['recommendation']}")
    print(f"  report: {path}")
    if baseline["hard_failures"] or comparison["embedding_hard_failures"]:
        return 1
    print("memory_recall_eval_compare: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
