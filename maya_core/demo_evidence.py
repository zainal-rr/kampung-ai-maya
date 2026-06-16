from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from permission_policy import SECRET_PATTERNS


ROOT = Path(__file__).resolve().parent
DEFAULT_LOG_DIR = ROOT / "logs" / "demos"
EXPECTED_DEMOS = (
    "telegram_document",
    "memory_weekly",
    "self_heal",
    "artisan_project",
    "blender_maker",
)


@dataclass(frozen=True)
class EvidenceIssue:
    demo: str
    issue: str


def refresh_latest_demo_evidence(log_dir: Path = DEFAULT_LOG_DIR) -> dict[str, Any]:
    records = _passing_records(log_dir)
    demos: list[dict[str, Any]] = []
    issues: list[EvidenceIssue] = []
    for name in EXPECTED_DEMOS:
        record = records.get(name)
        if not record:
            issues.append(EvidenceIssue(name, "missing latest passing demo log"))
            continue
        demos.append(_latest_payload(name, record))
    payload = {
        "schema": "kampung-ai.demo-evidence.latest.v1",
        "passed": not issues,
        "expected_demos": list(EXPECTED_DEMOS),
        "demos": demos,
        "issues": [issue.__dict__ for issue in issues],
    }
    payload["issues"].extend(
        issue.__dict__
        for issue in validate_latest_demo_evidence(payload, log_dir=log_dir, include_public_files=False)
    )
    payload["passed"] = not payload["issues"]
    return payload


def write_latest_demo_files(payload: dict[str, Any], log_dir: Path = DEFAULT_LOG_DIR) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (log_dir / "latest.md").write_text(format_latest_markdown(payload), encoding="utf-8")


def validate_latest_demo_evidence(
    payload: dict[str, Any],
    log_dir: Path = DEFAULT_LOG_DIR,
    *,
    include_public_files: bool = True,
) -> list[EvidenceIssue]:
    issues: list[EvidenceIssue] = []
    demos = {demo.get("name"): demo for demo in payload.get("demos", [])}
    for name in EXPECTED_DEMOS:
        demo = demos.get(name)
        if not demo:
            issues.append(EvidenceIssue(name, "missing from latest demo index"))
            continue
        issues.extend(_validate_demo(demo, log_dir))
    if include_public_files:
        issues.extend(_secret_issues(log_dir / "latest.json", "latest.json", block_private_home=True))
        issues.extend(_secret_issues(log_dir / "latest.md", "latest.md", block_private_home=True))
    return issues


def load_latest(log_dir: Path = DEFAULT_LOG_DIR) -> dict[str, Any]:
    path = log_dir / "latest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def format_latest_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Latest Passing Demo Evidence", "", f"Status: {'PASS' if payload.get('passed') else 'FAIL'}", ""]
    lines.append("| Demo | Status | Replay log | Evidence | Criteria |")
    lines.append("| --- | --- | --- | --- | --- |")
    for demo in payload.get("demos", []):
        criteria = "; ".join(demo.get("criteria", []))
        lines.append(
            "| {name} | {status} | {log} | {evidence} | {criteria} |".format(
                name=demo.get("name", ""),
                status="PASS" if demo.get("passed") else "FAIL",
                log=demo.get("replay_log", ""),
                evidence=demo.get("evidence_path", ""),
                criteria=criteria,
            )
        )
    if payload.get("issues"):
        lines.extend(["", "## Issues"])
        lines.extend(f"- {issue.get('demo')}: {issue.get('issue')}" for issue in payload["issues"])
    return "\n".join(lines) + "\n"


def _passing_records(log_dir: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    records: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(log_dir.glob("*.json")):
        if path.name == "latest.json":
            continue
        payload = _read_json(path)
        name = payload.get("name")
        if name not in EXPECTED_DEMOS or not payload.get("passed"):
            continue
        records[name] = (path, payload)
    return records


def _latest_payload(name: str, record: tuple[Path, dict[str, Any]]) -> dict[str, Any]:
    path, payload = record
    replay_log = path.with_suffix(".md")
    rel_json = _rel(path)
    rel_replay = _rel(replay_log)
    return {
        "name": name,
        "title": payload.get("title", name),
        "passed": bool(payload.get("passed")),
        "json_log": rel_json,
        "replay_log": rel_replay,
        "evidence_path": rel_replay if replay_log.exists() else rel_json,
        "artifacts": payload.get("artifacts", []),
        "criteria": payload.get("criteria", []),
        "results": _redacted_results(payload.get("results", [])),
    }


def _validate_demo(demo: dict[str, Any], log_dir: Path) -> list[EvidenceIssue]:
    name = str(demo.get("name"))
    issues: list[EvidenceIssue] = []
    if not demo.get("passed"):
        issues.append(EvidenceIssue(name, "latest selected demo is not passing"))
    if not demo.get("criteria"):
        issues.append(EvidenceIssue(name, "missing pass/fail criteria"))
    if not demo.get("results"):
        issues.append(EvidenceIssue(name, "missing command results"))
    if any(not str(result.get("output", "")).strip() for result in demo.get("results", [])):
        issues.append(EvidenceIssue(name, "one or more commands lack captured output"))
    evidence = ROOT / str(demo.get("evidence_path", ""))
    if not demo.get("artifacts") and not evidence.exists():
        issues.append(EvidenceIssue(name, "missing artifact or evidence path"))
    issues.extend(_secret_issues(evidence, name))
    json_log = ROOT / str(demo.get("json_log", ""))
    issues.extend(_secret_issues(json_log, name))
    return issues


def _secret_issues(path: Path, demo: str, *, block_private_home: bool = False) -> list[EvidenceIssue]:
    if not path.exists() or path.is_dir():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    issues = [
        EvidenceIssue(demo, f"secret-shaped value matched {pattern.pattern} in {_rel(path)}")
        for pattern in SECRET_PATTERNS
        if pattern.search(text)
    ]
    if block_private_home and f"{Path.home()}/" in text:
        issues.append(EvidenceIssue(demo, f"private local home path found in {_rel(path)}"))
    return issues


def _redacted_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for result in results:
        item = dict(result)
        item["output"] = _redact_text(str(item.get("output", "")))
        clean.append(item)
    return clean


def _redact_text(text: str) -> str:
    return text.replace(str(Path.home()), "<user-home>")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = refresh_latest_demo_evidence() if args.refresh else load_latest()
    if args.refresh:
        write_latest_demo_files(payload)
    issues = validate_latest_demo_evidence(payload)
    print(format_latest_markdown({**payload, "issues": [issue.__dict__ for issue in issues], "passed": not issues}))
    raise SystemExit(1 if issues or not payload else 0)


if __name__ == "__main__":
    main()
