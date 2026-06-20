#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maya_core.c0_capability_baseline import (
    build_maya_domain_capability_manifest,
    build_openai_planner_llm,
    build_openai_semantic_evaluator,
    make_report,
    run_capability_baseline,
    scripted_planner_llm,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the C0 reversible-loop capability baseline.")
    parser.add_argument("--planner", choices=("openai", "openai-if-available", "scripted"), default="openai-if-available")
    parser.add_argument("--evaluator", choices=("openai", "openai-if-available", "none"), default="openai-if-available")
    parser.add_argument("--out", default="")
    parser.add_argument("--workspace-root", default="")
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N tasks; intended for smoke/debug.")
    args = parser.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    manifest = build_maya_domain_capability_manifest()
    if args.limit:
        from dataclasses import replace

        manifest = replace(manifest, tasks=manifest.tasks[: args.limit])

    planner_llm = None
    provider_status = "missing"
    model_config = {
        "provider": "openai" if args.planner.startswith("openai") else "scripted",
        "model": os.getenv("MAYA_C0_MODEL", "gpt-5.5") if args.planner.startswith("openai") else "scripted_c0",
        "temperature": 0.0,
        "seed": "c0-current",
    }
    if args.planner == "scripted":
        planner_llm = scripted_planner_llm()
        provider_status = "scripted"
    else:
        planner_llm = build_openai_planner_llm()
        if planner_llm is None:
            report = make_report(
                status="deferred",
                manifest=manifest,
                started_at=started,
                provider_status="deferred",
                evaluator_status="not_run",
                model_config=model_config,
                command=_command(),
                deferred_reason="missing OPENAI_API_KEY",
            )
            _write_or_print(report, args.out)
            return 2 if args.planner == "openai" else 0
        provider_status = "configured"

    evaluator = None
    evaluator_status = "none"
    if args.evaluator.startswith("openai"):
        evaluator = build_openai_semantic_evaluator()
        if evaluator is None:
            if args.evaluator == "openai":
                report = make_report(
                    status="deferred",
                    manifest=manifest,
                    started_at=started,
                    provider_status=provider_status,
                    evaluator_status="deferred",
                    model_config=model_config,
                    command=_command(),
                    deferred_reason="missing OPENAI_API_KEY for semantic evaluator",
                )
                _write_or_print(report, args.out)
                return 2
            evaluator_status = "semantic_review_required"
        else:
            evaluator_status = "openai"

    results, workspace_root = asyncio.run(
        run_capability_baseline(
            manifest,
            planner_llm=planner_llm,
            semantic_evaluator=evaluator,
            workspace_root=args.workspace_root or None,
        )
    )
    report = make_report(
        status="complete",
        manifest=manifest,
        started_at=started,
        provider_status=provider_status,
        evaluator_status=evaluator_status,
        model_config=model_config,
        command=_command(),
        results=results,
        workspace_root=workspace_root,
    )
    _write_or_print(report, args.out)
    return 0


def _write_or_print(report, out: str) -> None:
    payload = write_report(report, out or None)
    print(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _command() -> str:
    return " ".join(["python", "scripts/run_c0_capability_baseline.py", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
