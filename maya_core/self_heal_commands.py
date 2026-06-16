from __future__ import annotations

from maya_core.assistant_command_helpers import direct_key
from maya_core.self_heal_store import latest_self_heal_report, latest_self_heal_stages


async def handle_self_heal_status(db_path: str, text: str) -> str | None:
    key = direct_key(text)
    if key not in {
        "what broke",
        "what did you test",
        "what patch are you proposing",
        "is it safe to restart",
        "show the repair report",
    }:
        return None
    report = await latest_self_heal_report(db_path)
    report_id = int(report["id"]) if report else None
    stages = await latest_self_heal_stages(db_path, limit=6, report_id=report_id)
    if not report and not stages:
        return "No self-heal report is open right now."
    if key == "is it safe to restart":
        return "Not yet. Maya still needs explicit approval before any restart."
    lines = []
    if report:
        lines.extend([
            f"Issue: {report['issue']}",
            f"Diagnosis: {report['diagnosis']}",
            f"Patch direction: {report['proposed_fix']}",
            f"Tests: {report['tests']}",
        ])
    if stages:
        lines.append("Stages:")
        lines.extend(f"{item['status']}: {item['details']}" for item in stages)
    return "\n".join(lines)
