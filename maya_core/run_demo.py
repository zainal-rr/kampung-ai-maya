from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs" / "demos"


@dataclass(frozen=True)
class Demo:
    name: str
    title: str
    criteria: tuple[str, ...]
    commands: tuple[tuple[str, ...], ...]


DEMOS = {
    "telegram_document": Demo(
        "telegram_document",
        "Telegram document creation",
        (
            "Word, Excel, and PowerPoint document-quality smokes pass.",
            "Route and delivery continuity smokes pass.",
            "No live provider call is required in replay mode.",
        ),
        (
            ("tests/smokes/document_route_flow_smoke.py",),
            ("tests/smokes/word_golden_artifact_smoke.py",),
            ("tests/smokes/excel_golden_artifact_smoke.py",),
            ("tests/smokes/pptx_quality_gate_smoke.py",),
            ("tests/smokes/telegram_delivery_file_smoke.py",),
        ),
    ),
    "memory_weekly": Demo(
        "memory_weekly",
        "Memory save/forget and weekly distillation",
        (
            "Canonical memory save/recall/forget works.",
            "Memory command cleanup prevents forgotten-value leaks.",
            "Weekly memory dry run completes without live provider calls.",
            "Nightly consolidation proves no-resurrect, association links, decay report, and zero-delta skip.",
        ),
        (("tests/smokes/canonical_memory_smoke.py",), ("tests/smokes/memory_control_smoke.py",), ("tests/smokes/weekly_memory_smoke.py",), ("tests/smokes/nightly_consolidation_smoke.py",)),
    ),
    "self_heal": Demo(
        "self_heal",
        "Approval-gated self-heal",
        (
            "Self-heal proposal/report path works.",
            "Memory self-heal dry-run/proceed guardrails pass.",
            "Complex agentic workflow pauses for approval and resumes safely.",
        ),
        (("tests/smokes/self_healing_smoke.py",), ("tests/smokes/self_heal_memory_smoke.py",), ("tests/smokes/complex_agentic_workflow_smoke.py",)),
    ),
    "artisan_project": Demo(
        "artisan_project",
        "Artisan project/app handoff",
        (
            "Artisan runner captures workflow state.",
            "App QA rejects broken assets and accepts complete projects.",
            "Latest-app delivery packages a Telegram-ready zip.",
        ),
        (("tests/smokes/artisan_runner_smoke.py",), ("tests/smokes/artisan_app_qa_smoke.py",), ("tests/smokes/artisan_delivery_smoke.py",)),
    ),
    "blender_maker": Demo(
        "blender_maker",
        "Blender/Maker printable output",
        (
            "Maker templates create deterministic source/export records.",
            "Blender can export real .blend and .stl files when available.",
            "Delivery summary includes safety status and no physical print action.",
        ),
        (("tests/smokes/artisan_maker_template_smoke.py",), ("tests/smokes/blender_maker_smoke.py",), ("tests/smokes/artisan_delivery_smoke.py",)),
    ),
}


def run_demo(name: str) -> dict:
    demo = DEMOS[name]
    started = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    results = [_run_command(command) for command in demo.commands]
    passed = all(result["passed"] for result in results)
    payload = {
        "name": demo.name,
        "title": demo.title,
        "started_at": started,
        "passed": passed,
        "criteria": list(demo.criteria),
        "results": results,
        "artifacts": [],
    }
    log_path = _write_log(demo, payload)
    payload["log_path"] = str(log_path)
    return payload


def format_demo_result(payload: dict) -> str:
    status = "PASS" if payload["passed"] else "FAIL"
    lines = [f"{status}: {payload['title']}", f"log: {payload['log_path']}", "criteria:"]
    for item in payload["criteria"]:
        lines.append(f"- {item}")
    for result in payload["results"]:
        lines.append(f"- {'PASS' if result['passed'] else 'FAIL'} {result['command']}")
    return "\n".join(lines)


def _run_command(command: tuple[str, ...]) -> dict:
    env = os.environ.copy()
    env.setdefault("MAYA_TEST_MODE", "1")
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not current_pythonpath else f"{ROOT}{os.pathsep}{current_pythonpath}"
    proc = subprocess.run([sys.executable, *command], cwd=ROOT, capture_output=True, text=True, env=env, timeout=120)
    output = (proc.stdout + proc.stderr).strip()
    return {
        "command": " ".join(command),
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "output": output[-4000:],
    }


def _write_log(demo: Demo, payload: dict) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    base = LOG_DIR / f"{demo.name}-{stamp}"
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(demo, payload, json_path), encoding="utf-8")
    return md_path


def _markdown(demo: Demo, payload: dict, json_path: Path) -> str:
    lines = [f"# Demo Replay: {demo.title}", "", f"Status: {'PASS' if payload['passed'] else 'FAIL'}", f"JSON: {json_path}", "", "## Criteria"]
    lines.extend(f"- {item}" for item in demo.criteria)
    lines.append("\n## Steps")
    for result in payload["results"]:
        lines.append(f"- {'PASS' if result['passed'] else 'FAIL'} `{result['command']}`")
    lines.append("\n## Outputs")
    for result in payload["results"]:
        lines.append(f"### `{result['command']}`\n```text\n{result['output']}\n```")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("demo", choices=sorted(DEMOS))
    args = parser.parse_args()
    payload = run_demo(args.demo)
    print(format_demo_result(payload))
    raise SystemExit(0 if payload["passed"] else 1)


if __name__ == "__main__":
    main()
