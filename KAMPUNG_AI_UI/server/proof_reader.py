"""Proof and readiness projections for the read-only Maya UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _json(path: str) -> dict[str, Any]:
    target = ROOT / path
    if not target.exists():
        return {"missing": True, "path": path}
    try:
        data = json.loads(target.read_text())
    except json.JSONDecodeError as exc:
        return {"error": str(exc), "path": path}
    if isinstance(data, dict):
        data.setdefault("path", path)
        return data
    return {"value": data, "path": path}


def _status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or item.get("live_status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _recent_failures(eval_log: dict[str, Any], live_log: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for result in eval_log.get("results", [])[:80]:
        if not result.get("passed", False):
            failures.append({
                "source": "eval",
                "name": str(result.get("name") or "check"),
                "detail": str(result.get("output") or "")[:180],
            })
    for item in live_log.get("items", [])[:80]:
        if str(item.get("status")) in {"failed", "manual-live-required", "pending"}:
            failures.append({
                "source": "live",
                "name": str(item.get("title") or item.get("id") or "live proof"),
                "detail": str(item.get("evidence") or item.get("notes") or "")[:180],
            })
    return failures[:12]


def proof_snapshot() -> dict[str, Any]:
    eval_log = _json("logs/evals/latest.json")
    demo_log = _json("logs/demos/latest.json")
    live_log = _json("logs/live_tests/latest.json")
    browser_log = _json("logs/browser_benchmarks/latest.json")
    health_log = _json("logs/health.json")
    eval_total = int(eval_log.get("total") or 0)
    eval_passed = int(eval_log.get("passed") or 0)
    eval_score = float(eval_log.get("score") or (eval_passed / eval_total * 100 if eval_total else 0))
    demos = demo_log.get("demos", []) if isinstance(demo_log.get("demos"), list) else []
    live_items = live_log.get("items", []) if isinstance(live_log.get("items"), list) else []
    browser_summary = browser_log.get("summary", {}) if isinstance(browser_log.get("summary"), dict) else {}
    return {
        "overall": {
            "score": round(min(100.0, (eval_score + float(browser_summary.get("live_score") or 0)) / 2), 1)
            if browser_summary else round(eval_score, 1),
            "label": "deterministic + live evidence",
        },
        "deterministic": {
            "score": round(eval_score, 1),
            "passed": eval_passed,
            "failed": int(eval_log.get("failed") or 0),
            "total": eval_total,
            "path": eval_log.get("path"),
            "created_at": eval_log.get("created_at"),
        },
        "demos": {
            "passed": bool(demo_log.get("passed")),
            "count": len(demos),
            "items": [
                {
                    "name": item.get("name"),
                    "passed": bool(item.get("passed")),
                    "log": item.get("replay_log") or item.get("evidence_path"),
                }
                for item in demos[:8]
            ],
            "path": demo_log.get("path"),
        },
        "live": {
            "updated_at": live_log.get("updated_at"),
            "counts": _status_counts(live_items),
            "items": live_items[:10],
            "path": live_log.get("path"),
        },
        "browser": {
            "summary": browser_summary,
            "path": browser_log.get("path"),
        },
        "health": health_log,
        "recent_failures": _recent_failures(eval_log, live_log),
    }
