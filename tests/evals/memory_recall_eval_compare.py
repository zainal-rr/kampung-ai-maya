from __future__ import annotations

"""Compare canonical-memory recall with and without embedding rerank."""

import asyncio
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


async def _run_with_flag(flag: str) -> dict[str, object]:
    old_value = os.environ.get("MEMORY_EMBED_RERANK_LIVE")
    os.environ["MEMORY_EMBED_RERANK_LIVE"] = flag
    try:
        report = await run_eval()
    finally:
        if old_value is None:
            os.environ.pop("MEMORY_EMBED_RERANK_LIVE", None)
        else:
            os.environ["MEMORY_EMBED_RERANK_LIVE"] = old_value
    report["rerank_flag"] = flag
    return report


def _comparison(baseline: dict[str, object], rerank: dict[str, object]) -> dict[str, object]:
    base_metrics = baseline["metrics"]
    rerank_metrics = rerank["metrics"]
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
            "lexical_neighbor_supersede_embedding_rerank",
        ),
        "baseline_hard_failures": baseline["hard_failures"],
        "embedding_hard_failures": rerank["hard_failures"],
        "baseline_supersede": baseline.get("supersede_scenarios", []),
        "embedding_supersede": rerank.get("supersede_scenarios", []),
        "metrics": rows,
        "recommendation": _recommendation(baseline, rerank),
    }


def _recommendation(baseline: dict[str, object], rerank: dict[str, object]) -> str:
    if rerank["hard_failures"]:
        return "keep_embedding_rerank_off: embedding run has hard failures"
    base = baseline["metrics"]
    emb = rerank["metrics"]
    if emb["forgotten"]["leaks"] or emb["absent"]["false_direct_recalls"]:
        return "keep_embedding_rerank_off: leakage or false direct recall detected"
    gains = []
    regressions = []
    for category in ("exact", "paraphrase", "malay_manglish", "voice_noisy", "temporal_old"):
        b = float(base.get(category, {}).get("recall_at_3", 0))
        e = float(emb.get(category, {}).get("recall_at_3", 0))
        if e > b:
            gains.append(category)
        elif e < b:
            regressions.append(category)
    if regressions:
        return f"keep_embedding_rerank_off: regressions in {', '.join(regressions)}"
    if gains:
        return f"candidate_for_default_after_latency_review: gains in {', '.join(gains)}"
    return "keep_embedding_rerank_off: no recall improvement"


def _report_path() -> Path:
    out_dir = _ROOT / "logs" / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return out_dir / f"memory_recall_eval_compare-{stamp}.json"


async def _main() -> int:
    baseline = await _run_with_flag("0")
    rerank = await _run_with_flag("1")
    report = {
        "baseline": baseline,
        "embedding_rerank": rerank,
        "comparison": _comparison(baseline, rerank),
    }
    path = _report_path()
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    comparison = report["comparison"]
    print(f"Memory recall compare ({baseline['cases']} cases)")
    print(f"  baseline hard failures: {len(comparison['baseline_hard_failures'])}")
    print(f"  embedding hard failures: {len(comparison['embedding_hard_failures'])}")
    for category, values in comparison["metrics"].items():
        print(f"  {category}: baseline={values['baseline']} embedding={values['embedding']}")
    print(f"  recommendation: {comparison['recommendation']}")
    print(f"  report: {path}")
    if baseline["hard_failures"] or rerank["hard_failures"]:
        return 1
    print("memory_recall_eval_compare: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
