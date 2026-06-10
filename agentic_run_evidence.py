from __future__ import annotations

"""Evidence records for live agentic reliability scenarios.

A scenario record captures: the scripted turns with Maya's verbatim replies,
every harness run the scenario created (status + checkpointed events),
artifacts with on-disk verification, approval rows, and the final
pass/partial/fail label. Written as append-only JSONL like the browser nights.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import aiosqlite

from browser_run_evidence import redact, utc_now


AGENTIC_RELIABILITY_DIR = Path("logs") / "live_tests" / "agentic"
MAX_REPLY = 2000


@dataclass
class ScenarioRecord:
    scenario_id: str
    night_id: str
    title: str
    turns: list = field(default_factory=list)
    run_ids: list = field(default_factory=list)
    workflow_types: list = field(default_factory=list)
    statuses: dict = field(default_factory=dict)
    events: dict = field(default_factory=dict)
    artifacts: list = field(default_factory=list)
    approvals: list = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    status: str = "not-run"
    reasons: list = field(default_factory=list)


def new_scenario_record(scenario_id: str, night_id: str, title: str) -> ScenarioRecord:
    return ScenarioRecord(scenario_id, night_id, title, started_at=utc_now())


def add_turn(record: ScenarioRecord, text: str, kind: str, reply: str) -> None:
    record.turns.append({"at": utc_now(), "kind": kind, "text": text, "reply": (reply or "")[:MAX_REPLY]})


async def existing_run_ids(db_path: str) -> set[str]:
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT run_id FROM harness_runs")
            return {row[0] for row in await cursor.fetchall()}
    except Exception:  # noqa: BLE001 - table may not exist before the first run
        return set()


async def collect_scenario_state(record: ScenarioRecord, db_path: str, before: set[str]) -> None:
    from harness_artifact_store import latest_artifacts
    from harness_store import get_run, latest_events

    record.run_ids = sorted(await existing_run_ids(db_path) - before)
    for run_id in record.run_ids:
        run = await get_run(db_path, run_id) or {}
        record.statuses[run_id] = str(run.get("status", "unknown"))
        if run.get("workflow_type"):
            record.workflow_types.append(str(run["workflow_type"]))
        record.events[run_id] = [
            {"event": item["event"], "details": item["details"]}
            for item in await latest_events(db_path, run_id, limit=24)
        ]
        for artifact in await latest_artifacts(db_path, run_id, limit=6):
            path = str(artifact.get("path") or "")
            exists = bool(path) and Path(path).exists()
            record.artifacts.append(
                {
                    "run_id": run_id,
                    "kind": str(artifact.get("kind", "")),
                    "path": path,
                    "exists": exists,
                    "size": Path(path).stat().st_size if exists else 0,
                }
            )
    record.approvals = await _approvals(db_path, record.run_ids)
    record.finished_at = utc_now()


async def _approvals(db_path: str, run_ids: list[str]) -> list[dict]:
    if not run_ids:
        return []
    marks = ",".join("?" for _ in run_ids)
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                f"SELECT run_id, action, status FROM harness_approvals WHERE run_id IN ({marks})",
                run_ids,
            )
            return [
                {"run_id": row[0], "action": row[1], "status": row[2]}
                for row in await cursor.fetchall()
            ]
    except Exception:  # noqa: BLE001
        return []


def scenario_to_dict(record: ScenarioRecord) -> dict:
    return _redact_value(asdict(record))


def append_scenario(record: ScenarioRecord, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(scenario_to_dict(record), ensure_ascii=False) + "\n")


def load_scenarios(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def agentic_night_summary(rows: list[dict]) -> dict:
    statuses = {"pass": 0, "partial": 0, "fail": 0}
    for row in rows:
        statuses[row.get("status") if row.get("status") in statuses else "fail"] += 1
    total = len(rows)
    return {
        "total": total,
        **statuses,
        "completion_rate": round(statuses["pass"] / total * 100, 1) if total else 0.0,
        "false_saved_criticals": _count(rows, "critical:false-saved"),
        "approval_criticals": _count(rows, "critical:approval"),
        "lost_state_criticals": _count(rows, "critical:lost-state"),
        "honesty_criticals": _count(rows, "critical:honesty"),
    }


def write_agentic_markdown(rows: list[dict], path: Path) -> None:
    summary = agentic_night_summary(rows)
    lines = [
        f"# Agentic Reliability Night {rows[0]['night_id'] if rows else ''}",
        "",
        f"completion: {summary['completion_rate']}% ({summary['pass']}/{summary['total']}) | "
        f"false-saved: {summary['false_saved_criticals']} | approval: {summary['approval_criticals']} | "
        f"lost-state: {summary['lost_state_criticals']} | honesty: {summary['honesty_criticals']}",
        "",
    ]
    for row in rows:
        lines.append(f"## {row['scenario_id']} [{row.get('status', '?').upper()}] {row.get('title', '')}")
        for turn in row.get("turns", []):
            lines.append(f"- {turn['kind']}: {turn['text']}")
            lines.append(f"  reply: {turn['reply'][:220]}")
        for run_id in row.get("run_ids", []):
            lines.append(f"run {run_id}: status={row['statuses'].get(run_id)} events={len(row['events'].get(run_id, []))}")
        for artifact in row.get("artifacts", []):
            lines.append(f"artifact: {artifact['path']} exists={artifact['exists']} size={artifact['size']}")
        for reason in row.get("reasons", []):
            lines.append(f"reason: {reason}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", "utf-8")


def _count(rows: list[dict], prefix: str) -> int:
    return sum(1 for row in rows if any(str(reason).startswith(prefix) for reason in row.get("reasons", [])))


def _redact_value(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    return value
