from __future__ import annotations

from html import escape

from approval_inbox import approval_items
from cost_tracker import usage_summary_text
from harness_artifact_store import latest_artifacts
from mcp_registry import recent_mcp_usage
from skill_outcome_store import recent_skill_outcomes
from skill_store import list_custom_skills, list_skill_proposals
from user_model_store import list_user_model_items
from workflow_desk import workflow_desk_text
from workspace_paths import workspace_dir


async def build_maya_desk(db_path: str) -> str:
    report = workspace_dir("reports", create=True) / "maya-desk.html"
    html = await _html(db_path)
    report.write_text(html, "utf-8")
    return str(report)


async def maya_desk_text(db_path: str) -> str:
    path = await build_maya_desk(db_path)
    return f"Maya desk refreshed: {path}\n[file:{path}]"


async def _html(db_path: str) -> str:
    workflows = escape(await workflow_desk_text(db_path))
    approvals = await approval_items(db_path)
    artifacts = await latest_artifacts(db_path, limit=8)
    active = await list_custom_skills(db_path, status="active", limit=8)
    proposed = await list_skill_proposals(db_path, limit=8)
    disabled = await list_custom_skills(db_path, status="disabled", limit=8)
    user_model = await list_user_model_items(db_path, limit=8)
    mcp = await recent_mcp_usage(db_path, limit=8)
    outcomes = await recent_skill_outcomes(db_path, limit=8)
    cost = escape(await usage_summary_text(db_path))
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Maya Desk</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #14351f; }}
section {{ border: 1px solid #ccd8c8; border-radius: 8px; padding: 16px; margin: 14px 0; }}
h1, h2 {{ margin: 0 0 10px; }}
li {{ margin: 6px 0; }}
pre {{ white-space: pre-wrap; }}
</style>
</head>
<body>
<h1>Maya Desk</h1>
<section><h2>Workflows</h2><pre>{workflows}</pre></section>
{_section("Approvals", approvals)}
{_section("Artifacts", [f"{a.get('kind')}: {a.get('path') or a.get('url')}" for a in artifacts])}
{_section("Active Skills", [s["name"] for s in active])}
{_section("Proposed Skills", [p["summary"] for p in proposed])}
{_section("Disabled Skills", [s["name"] for s in disabled])}
{_section("User Model", [f"{u['category']}: {u['content']}" for u in user_model])}
{_section("MCP Usage", [f"{e['name']}: {e['action']}" for e in mcp])}
{_section("Recent Skill Outcomes", [f"{o['skill_id']}: {o['outcome']}" for o in outcomes])}
<section><h2>Cost</h2><pre>{cost}</pre></section>
</body>
</html>"""


def _section(title: str, items: list[str]) -> str:
    lis = "".join(f"<li>{escape(str(item))}</li>" for item in items[:12]) or "<li>None</li>"
    return f"<section><h2>{escape(title)}</h2><ul>{lis}</ul></section>"
