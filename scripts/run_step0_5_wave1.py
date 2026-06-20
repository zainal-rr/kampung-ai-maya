#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maya_core.step0_5_wave1_binding import (
    SCOPE,
    Step05Wave1Executor,
    build_gemini_reader_llm,
    build_openai_planner_llm,
    build_wave1_manifest,
    deterministic_wave1_llm,
)
from maya_core.whole_loop_harness import report_to_dict, run_manifest
from maya_core.whole_loop_harness_models import ModelConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Step 0.5 sealed Wave 1 through the runnable binding.")
    parser.add_argument("--planner", choices=("deterministic", "openai"), default="openai")
    parser.add_argument("--reader", choices=("projection", "gemini", "gemini-if-available"), default="gemini-if-available")
    parser.add_argument("--runs-per-case", type=int, default=3)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    parser.add_argument("--seed", default="wave1-current")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    planner_llm = deterministic_wave1_llm()
    provider = "deterministic"
    model = "step0_5_smoke"
    deterministic_replay = True
    provider_status = "deterministic"
    if args.planner == "openai":
        planner_llm = build_openai_planner_llm()
        if planner_llm is None:
            payload = {
                "status": "deferred",
                "reason": "missing OPENAI_API_KEY",
                "scope": SCOPE,
                "planner": "openai",
                "reader": args.reader,
                "created_at": started,
            }
            _write_or_print(payload, args.out)
            return 2
        provider = "openai"
        model = os.getenv("MAYA_STEP0_5_MODEL", "gpt-5.5")
        deterministic_replay = False
        provider_status = "configured"

    reader_llm = None
    reader_mode = "projection"
    reader_status = "projection"
    if args.reader in {"gemini", "gemini-if-available"}:
        reader_llm = build_gemini_reader_llm()
        if reader_llm is None and args.reader == "gemini":
            payload = {
                "status": "deferred",
                "reason": "missing GOOGLE_API_KEY",
                "scope": SCOPE,
                "planner": args.planner,
                "reader": args.reader,
                "created_at": started,
            }
            _write_or_print(payload, args.out)
            return 2
        if reader_llm is not None:
            reader_mode = "provider"
            reader_status = "gemini"

    manifest = build_wave1_manifest(timeout_s=args.timeout_s)
    executor = Step05Wave1Executor(planner_llm=planner_llm, reader_llm=reader_llm, reader_mode=reader_mode)
    report = run_manifest(
        manifest,
        executor,
        runs_per_case=args.runs_per_case,
        seed=args.seed,
        model_config=ModelConfig(provider=provider, model=model, temperature=0.0, seed=args.seed),
    )
    payload = report_to_dict(report)
    payload.update(
        {
            "status": "complete",
            "created_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "product_commit": _git("rev-parse", "HEAD"),
            "branch": _git("branch", "--show-current"),
            "deterministic_replay": deterministic_replay,
            "provider_status": provider_status,
            "reader_status": reader_status,
            "scope": SCOPE,
            "safe_effect_sink": True,
            "command": " ".join(["python", "scripts/run_step0_5_wave1.py", *os.sys.argv[1:]]),
        }
    )
    _write_or_print(payload, args.out)
    return 0


def _write_or_print(payload: dict, out: str) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if out:
        target = Path(out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(text)


def _git(*args: str) -> str:
    try:
        proc = subprocess.run(("git", *args), check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return proc.stdout.strip()
    except Exception:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
