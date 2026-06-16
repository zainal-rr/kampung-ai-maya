from __future__ import annotations

from pathlib import Path

from maya_core.security_manifest import SecurityManifest, upsert_manifest
from skill_learning_store import upsert_skill_metadata
from skill_library import proposed_path
from skill_store import init_skill_db, upsert_skill


CATALOG = {
    "flight_research": ("Flight Research", "Compare flights and stop before booking.", ["flight", "airport", "date"], ["submit", "card"]),
    "shopping_comparison": ("Shopping Comparison", "Compare products and stop before checkout.", ["product", "price", "reviews"], ["checkout", "payment"]),
    "browser_research": ("Browser Research", "Research sources and create notes.", ["research", "source", "summarize"], ["private data"]),
    "document_critique": ("Document Critique", "Review Word or markdown documents.", ["review document", "critique draft"], ["send"]),
    "slide_critique": ("Slide Critique", "Review presentation clarity and structure.", ["review slide", "critique ppt"], ["send"]),
    "network_troubleshooting": ("Network Troubleshooting", "Inspect network symptoms and draft steps.", ["network down", "router"], ["password"]),
    "finance_tracker": ("Finance Tracker", "Create safe finance trackers without sensitive data.", ["budget", "cost"], ["bank", "card"]),
    "habit_planning": ("Habit Planning", "Create habit plans and routines.", ["habit", "routine"], ["medical diagnosis"]),
    "app_control": ("App Control", "Open and switch local apps safely.", ["open app", "switch app"], ["delete"]),
    "excel_tracker": ("Excel Tracker", "Create simple spreadsheets and trackers.", ["spreadsheet", "xlsx"], ["secrets"]),
}


async def install_starter_catalog(db_path: str, root: Path | None = None) -> int:
    await init_skill_db(db_path)
    count = 0
    for skill_id, (name, description, triggers, stops) in CATALOG.items():
        path = proposed_path(skill_id, root)
        if not path.exists():
            path.write_text(_skill_text(name, description, triggers, stops), "utf-8")
        await upsert_skill(
            db_path, skill_id, name, description, "bounded", "approval_required",
            "proposed", "starter_catalog", str(path),
        )
        await upsert_skill_metadata(
            db_path,
            skill_id,
            triggers=triggers,
            non_triggers=stops,
            tools_needed=_tools_for(skill_id),
            safety_boundary="Starter skill. Requires tests and approval before activation.",
            test_commands=["trigger", "non_trigger", "safety", "happy_path", "failure_path", "regression"],
        )
        await upsert_manifest(db_path, _manifest_for(skill_id))
        count += 1
    return count


def catalog_summary() -> str:
    lines = [f"{idx}) {name}: {description}" for idx, (_, (name, description, _, _)) in enumerate(CATALOG.items(), 1)]
    return "Starter skill catalog:\n" + "\n".join(lines)


def _skill_text(name: str, description: str, triggers: list[str], stops: list[str]) -> str:
    trigger_lines = "\n".join(f"- {item}" for item in triggers)
    stop_lines = "\n".join(f"- {item}" for item in stops)
    return f"""# {name}

Description: {description}

## Trigger Phrases
{trigger_lines}

## Non Triggers And Safety Stops
{stop_lines}

## Activation
Proposed starter skill. Run required tests and get approval before activation.
"""


def _tools_for(skill_id: str) -> list[str]:
    if "browser" in skill_id or "flight" in skill_id or "shopping" in skill_id:
        return ["browser", "screen", "artifact_store"]
    if "excel" in skill_id or "finance" in skill_id:
        return ["spreadsheet_writer", "artifact_store"]
    if "critique" in skill_id:
        return ["file_reader", "steward_review"]
    return ["maya_core"]


def _manifest_for(skill_id: str) -> SecurityManifest:
    perms = {"create_artifacts": True}
    if skill_id in {"flight_research", "shopping_comparison", "browser_research"}:
        perms.update({"browse_web": True, "browser_click": True})
    if skill_id in {"excel_tracker", "finance_tracker"}:
        perms.update({"write_files": True})
    if skill_id in {"document_critique", "slide_critique"}:
        perms.update({"read_files": True})
    if skill_id == "app_control":
        perms.update({"browser_click": True})
    return SecurityManifest(
        "skill", skill_id, perms,
        hard_blocks=["private_exposure", "secrets", "payment_without_confirmation"],
        notes="Starter catalog skill.",
    )
