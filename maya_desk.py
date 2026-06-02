from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from approval_inbox import approval_items
from cost_tracker import usage_summary_text
from curated_memory import curated_memory_status
from demo_evidence import load_latest
from dependency_manifest import dependency_statuses, readiness_summary
from hardening_audit import hardening_audit_summary, route_cost_audit
from harness_artifact_store import latest_artifacts
from maya_event_store import MayaEventStore
from mcp_registry import recent_mcp_usage
from route_tracker import last_route_text
from self_heal_store import latest_self_heal_report
from skill_outcome_store import recent_skill_outcomes
from skill_store import list_custom_skills, list_skill_proposals
from user_model_store import list_user_model_items
from weekly_memory_status import weekly_memory_status_text
from workflow_desk import workflow_desk_text
from workspace_paths import workspace_dir


async def build_maya_desk(db_path: str) -> str:
    report = workspace_dir("reports", create=True) / "maya-desk.html"
    report.write_text(await _html(db_path), "utf-8")
    return str(report)


async def maya_desk_text(db_path: str) -> str:
    path = await build_maya_desk(db_path)
    return f"Maya desk refreshed: {path}\n[file:{path}]"


async def _html(db_path: str) -> str:
    approvals = await approval_items(db_path)
    artifacts = await latest_artifacts(db_path, limit=8)
    active = await list_custom_skills(db_path, status="active", limit=8)
    proposed = await list_skill_proposals(db_path, limit=8)
    disabled = await list_custom_skills(db_path, status="disabled", limit=8)
    user_model = await list_user_model_items(db_path, limit=8)
    mcp = await recent_mcp_usage(db_path, limit=8)
    outcomes = await recent_skill_outcomes(db_path, limit=8)
    deps = dependency_statuses()
    dep_summary = readiness_summary()
    eval_payload = _latest_eval()
    demo_payload = load_latest()
    self_heal = await latest_self_heal_report(db_path)
    events = await MayaEventStore(db_path).list(limit=12)
    generated = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Maya Desk</title>
<style>{_css()}</style>
</head>
<body>
<h1>Maya Desk</h1>
<p>Generated: {escape(generated)}</p>
<section><h2>Readiness</h2><div class="grid">
<div class="card"><strong>Eval Score</strong><br>{_eval_badge(eval_payload)}</div>
<div class="card"><strong>Dependencies</strong><br>{_status_badge(dep_summary.get("missing", 0) == 0, str(dep_summary))}</div>
<div class="card"><strong>Approvals</strong><br>{_status_badge(not approvals, f"{len(approvals)} pending")}</div>
<div class="card"><strong>Recent Self Heal</strong><br>{escape(str(self_heal.get("issue") if self_heal else "none"))}</div>
</div></section>
<section><h2>Workflows</h2><pre>{escape(await workflow_desk_text(db_path))}</pre></section>
<section><h2>Last Route</h2><pre>{escape(await last_route_text(db_path))}</pre></section>
<section><h2>Memory Health</h2><pre>{escape(await curated_memory_status(db_path))}</pre></section>
<section><h2>Weekly Memory</h2><pre>{escape(await weekly_memory_status_text(db_path))}</pre></section>
{_section("Dependency Readiness", [f"{d.id}: {d.status} ({d.requirement})" for d in deps])}
{_section("Provider Readiness", _provider_items(deps))}
{_section("Latest Passing Demos", _latest_demo_items(demo_payload))}
{_section("Route And Cost Audit", [f"{i.name}: {'PASS' if i.passed else 'CHECK'} | {i.detail}" for i in route_cost_audit()])}
<section><h2>Hardening Audit</h2><pre>{escape(hardening_audit_summary())}</pre></section>
{_section("Harness Traces", [f"{e['created_at']} {e['thread_id']} {e['event_type']}: {e['summary']}" for e in events])}
{_section("Recent Failures", _failure_items(eval_payload, self_heal))}
{_section("Approvals", approvals)}
{_section("Artifacts", [f"{a.get('kind')}: {a.get('path') or a.get('url')}" for a in artifacts])}
{_section("Active Skills", [s["name"] for s in active])}
{_section("Proposed Skills", [p["summary"] for p in proposed])}
{_section("Disabled Skills", [s["name"] for s in disabled])}
{_section("User Model", [f"{u['category']}: {u['content']}" for u in user_model])}
{_section("MCP Usage", [f"{e['name']}: {e['action']}" for e in mcp])}
{_section("Recent Skill Outcomes", [f"{o['skill_id']}: {o['outcome']}" for o in outcomes])}
<section><h2>Cost</h2><pre>{escape(await usage_summary_text(db_path))}</pre></section>
</body>
</html>"""


def _css() -> str:
    return (
        "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:32px;color:#14351f;background:#f7faf5}"
        "section{border:1px solid #ccd8c8;border-radius:8px;padding:16px;margin:14px 0;background:#fff}"
        "h1,h2{margin:0 0 10px}li{margin:6px 0}pre{white-space:pre-wrap}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}"
        ".card{border:1px solid #dce6d8;border-radius:8px;padding:12px;background:#fbfdf9}"
        ".pass{color:#116329;font-weight:700}.warn{color:#9a6700;font-weight:700}"
    )


def _section(title: str, items: list[str]) -> str:
    lis = "".join(f"<li>{escape(str(item))}</li>" for item in items[:12]) or "<li>None</li>"
    return f"<section><h2>{escape(title)}</h2><ul>{lis}</ul></section>"


def _latest_eval() -> dict:
    path = Path("logs/evals/latest.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _latest_demo_items(payload: dict) -> list[str]:
    if not payload:
        return ["No latest demo evidence found."]
    items = [
        f"{demo.get('name')}: {'PASS' if demo.get('passed') else 'FAIL'} | {demo.get('evidence_path')}"
        for demo in payload.get("demos", [])
    ]
    if payload.get("issues"):
        items.extend(f"issue: {issue.get('demo')} - {issue.get('issue')}" for issue in payload["issues"])
    return items


def _provider_items(deps: list) -> list[str]:
    return [f"{d.id}: {d.status} ({d.detail})" for d in deps if d.category == "provider_key"]


def _eval_badge(payload: dict) -> str:
    if not payload:
        return '<span class="warn">No eval run found</span>'
    text = f"{payload.get('score', 0)}% ({payload.get('passed', 0)}/{payload.get('total', 0)})"
    return _status_badge(int(payload.get("failed", 0)) == 0, text)


def _status_badge(ok: bool, text: str) -> str:
    cls = "pass" if ok else "warn"
    label = "PASS" if ok else "CHECK"
    return f'<span class="{cls}">{label}</span> {escape(text)}'


def _failure_items(eval_payload: dict, self_heal: dict | None) -> list[str]:
    items = [
        f"{result.get('category')}: {result.get('name')}"
        for result in eval_payload.get("results", [])
        if not result.get("passed", False)
    ]
    if self_heal and self_heal.get("status") not in {"closed", "completed"}:
        items.append(f"self-heal: {self_heal.get('issue')}")
    return items
