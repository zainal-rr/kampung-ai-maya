from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "logs" / "evals" / "latest.json"


@dataclass(frozen=True)
class EvalCase:
    category: str
    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class EvalResult:
    category: str
    name: str
    passed: bool
    returncode: int
    output: str


EVAL_CASES = (
    EvalCase("routing", "route tracker", ("route_tracker_smoke.py",)),
    EvalCase("memory", "canonical memory", ("canonical_memory_smoke.py",)),
    EvalCase("memory", "self-heal memory", ("self_heal_memory_smoke.py",)),
    EvalCase("weekly_memory", "weekly memory dry run", ("weekly_memory_smoke.py",)),
    EvalCase("weekly_memory", "weekly provider path", ("weekly_memory_provider_path_smoke.py",)),
    EvalCase("research", "source-aware Gemini research", ("source_aware_research_smoke.py",)),
    EvalCase("memory", "Omi context sieve", ("omi_context_sieve_smoke.py",)),
    EvalCase("word", "word quality", ("word_quality_smoke.py",)),
    EvalCase("excel", "excel golden artifact", ("excel_golden_artifact_smoke.py",)),
    EvalCase("powerpoint", "pptx quality gate", ("pptx_quality_gate_smoke.py",)),
    EvalCase("documents", "Office edit workflow", ("document_edit_office_smoke.py",)),
    EvalCase("self_heal", "self-heal loop", ("self_heal_loop_smoke.py",)),
    EvalCase("quantum", "quantum leaf boundary", ("quantum_leaf_smoke.py",)),
    EvalCase("artisan", "artisan runner", ("artisan_runner_smoke.py",)),
    EvalCase("blender_maker", "maker template", ("artisan_maker_template_smoke.py",)),
    EvalCase("safety", "secret detection", ("secret_detection_smoke.py",)),
    EvalCase("maya_desk", "maya desk", ("maya_desk_smoke.py",)),
    EvalCase("harness", "harness SDK", ("maya_harness_sdk_smoke.py",)),
    EvalCase("harness", "thread manager", ("maya_thread_manager_smoke.py",)),
    EvalCase("harness", "event store", ("maya_event_store_smoke.py",)),
    EvalCase("harness", "tool registry", ("maya_tool_registry_smoke.py",)),
    EvalCase("harness", "permission kernel", ("maya_permission_kernel_smoke.py",)),
    EvalCase("dependencies", "dependency manifest", ("dependency_manifest_smoke.py",)),
    EvalCase("demos", "demo evidence", ("demo_evidence_smoke.py",)),
    EvalCase("hardening", "hardening audit", ("hardening_audit_smoke.py",)),
)


def run_eval_suite(output: Path = DEFAULT_OUTPUT, categories: set[str] | None = None) -> dict:
    selected = [case for case in EVAL_CASES if not categories or case.category in categories]
    results = [_run_case(case) for case in selected]
    passed = sum(1 for result in results if result.passed)
    payload = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "passed": passed,
        "failed": len(results) - passed,
        "total": len(results),
        "score": round((passed / len(results)) * 100, 1) if results else 0,
        "results": [asdict(result) for result in results],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def format_eval_summary(payload: dict) -> str:
    lines = [
        "Kampung AI eval suite:",
        f"1) score: {payload['score']}%",
        f"2) passed: {payload['passed']}/{payload['total']}",
        f"3) failed: {payload['failed']}",
    ]
    failures = [item for item in payload["results"] if not item["passed"]]
    if failures:
        lines.append("4) failures:")
        for item in failures:
            lines.append(f"- {item['category']} / {item['name']}: exit {item['returncode']}")
    else:
        lines.append("4) failures: none")
    return "\n".join(lines)


def _run_case(case: EvalCase) -> EvalResult:
    env = os.environ.copy()
    env.setdefault("MAYA_TEST_MODE", "1")
    proc = subprocess.run(
        [sys.executable, *case.command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    output = (proc.stdout + proc.stderr).strip()
    return EvalResult(case.category, case.name, proc.returncode == 0, proc.returncode, output[-2000:])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--category", action="append", default=[])
    args = parser.parse_args()
    payload = run_eval_suite(Path(args.output), set(args.category) or None)
    print(format_eval_summary(payload))
    raise SystemExit(1 if payload["failed"] else 0)


if __name__ == "__main__":
    main()
