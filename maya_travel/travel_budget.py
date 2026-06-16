"""Excel travel-budget builder used by document requests and follow-up edits.

This module is intentionally more specific than a generic spreadsheet creator.
For travel and food-trip budget workbooks it loads saved trip context, merges
active artifact-session context, asks Gemini for budget notes when needed, builds
the workbook locally, then sends the file through `ArtifactBuilder` for Excel
QA, Claude review when available, retry, latest-document tracking, and delivery.

The recent continuity fix is here: if the latest Word itinerary says "Tokyo,
2 days, 2 people" and the next turn asks for an Excel budget "for the itinerary",
the workbook inherits those parameters instead of defaulting back to one person.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from maya_documents.artifact_naming import named_artifact_path
from maya_documents.artifact_builder import ArtifactBuilder
from maya_documents.artifact_sessions import active_artifact_session

from markdown_drafter import draft_markdown_with_gemini
from storage import get_preference, upsert_preference
from utils import OSBridge
from workspace_paths import workspace_dir
from travel_budget_workbook import _build_workbook
from travel_budget_plan import (
    _current_trip_reference,
    _food_trip_request,
    _parse_plan_updates,
    _plan_reply,
    _template_plan,
    _template_request,
    _trip_specific_request,
)


TRAVEL_PLAN_KEY = "maya_travel_plan"
TRAVEL_BUDGET_RUN_ID = "travel_budget_planner"


@dataclass(frozen=True)
class TravelParty:
    count: int
    source: str
    participants: tuple[str, ...] = ()


async def update_travel_plan(db_path: str, text: str) -> str:
    plan = await _load_plan(db_path)
    changes = _parse_plan_updates(text)
    if changes:
        plan.update(changes)
    party = await infer_travel_party(db_path)
    if "people_count" not in plan:
        plan["people_count"] = party.count
        plan["people_source"] = party.source
    await upsert_preference(db_path, TRAVEL_PLAN_KEY, json.dumps(plan, ensure_ascii=False), source="travel")
    return _plan_reply(plan, changes, party)


async def save_travel_plan_fields(db_path: str, **fields: object) -> None:
    plan = await _load_plan(db_path)
    for key, value in fields.items():
        if value not in (None, ""):
            plan[key] = value
    await upsert_preference(db_path, TRAVEL_PLAN_KEY, json.dumps(plan, ensure_ascii=False), source="travel")


async def create_travel_budget_excel(
    db_path: str,
    request: str,
    bridge: OSBridge | None = None,
    channel: str = "imac",
    preflight_context: str = "",
) -> str:
    bridge = bridge or OSBridge()
    saved_plan = await _load_plan(db_path)
    parsed = _parse_plan_updates(request)
    context_plan = await _artifact_context_plan(db_path, channel, request, parsed)
    use_saved_context = _current_trip_reference(request) or not parsed.get("destination")
    plan = dict(saved_plan) if use_saved_context else {}
    if context_plan and _should_use_artifact_context(request, parsed, context_plan):
        for key, value in context_plan.items():
            if value not in (None, "") and key not in plan:
                plan[key] = value
    if parsed:
        plan.update(parsed)
    if _food_trip_request(request):
        plan["food_focus"] = True
        plan.setdefault("days", 2)
    party = await infer_travel_party(db_path)
    trip_specific = _trip_specific_request(request, parsed)
    template_mode = (_template_request(request) and not trip_specific) or not trip_specific
    if template_mode:
        plan = _template_plan()
    else:
        people_count = int(plan.get("people_count") or (party.count if use_saved_context else 1))
        plan["people_count"] = people_count
        plan.setdefault("people_source", party.source if use_saved_context else "default until traveler count is explicit")
        plan.setdefault("origin", "Kuala Lumpur")
        plan.setdefault("destination", "Osaka / Kyoto")
        plan.setdefault("departure_date", "")
        plan.setdefault("return_date", "")
        plan.setdefault("flight_preference", "not selected yet")
        plan.setdefault("accommodation_type", "not selected yet")
        plan.setdefault("accommodation_preference", "middle to high-end; hotel 4-5 star or Airbnb guest favourite")
        await upsert_preference(db_path, TRAVEL_PLAN_KEY, json.dumps(plan, ensure_ascii=False), source="travel")

    output_dir = workspace_dir("spreadsheets", create=True)
    if template_mode:
        path = named_artifact_path(output_dir, "travel-budget-template", "xlsx")
    else:
        destination = _slug(plan.get("destination", "trip"))
        path = named_artifact_path(output_dir, f"{destination} budget tracker", "xlsx")
    plan["gemini_notes"] = await _travel_budget_notes(db_path, request, plan, template_mode, preflight_context)
    _build_workbook(path, plan, party)
    label = "travel budget template" if template_mode else _traveler_phrase(plan)

    async def rebuild_workbook(attempt: int, quality) -> None:
        plan["gemini_notes"] = await _travel_budget_notes(
            db_path,
            f"{request}. Repair failed workbook QA attempt {attempt}: {quality.short_issue_text()}",
            plan,
            template_mode,
            preflight_context,
        )
        _build_workbook(path, plan, party)

    artifact = await ArtifactBuilder(db_path, bridge).finish_xlsx(
        path,
        request,
        channel,
        run_id=TRAVEL_BUDGET_RUN_ID,
        source_tool="travel_budget",
        label=f"an editable {label}",
        rebuild=rebuild_workbook,
    )
    return artifact.reply


async def infer_travel_party(db_path: str) -> TravelParty:
    plan = await _load_plan(db_path)
    if plan.get("people_count"):
        return TravelParty(max(1, int(plan["people_count"])), "saved travel plan")
    return TravelParty(1, "default until traveler count is explicit")


async def _artifact_context_plan(db_path: str, channel: str, request: str, parsed: dict) -> dict:
    try:
        session = await active_artifact_session(db_path, channel)
    except Exception:
        return {}
    if not session:
        return {}
    state = dict(session.state or {})
    plan: dict[str, object] = {}
    destination = state.get("destination") or state.get("subject")
    if destination:
        plan["destination"] = str(destination)
    if state.get("days"):
        plan["days"] = int(state["days"])
    if state.get("people"):
        plan["people_count"] = int(state["people"])
        plan["people_source"] = f"latest {session.artifact_type} context"
    return plan


def _should_use_artifact_context(request: str, parsed: dict, context_plan: dict) -> bool:
    lowered = str(request or "").lower()
    if _current_trip_reference(request) or "itinerary" in lowered or "latest" in lowered or "current" in lowered:
        return True
    parsed_destination = str(parsed.get("destination") or "").strip().lower()
    context_destination = str(context_plan.get("destination") or "").strip().lower()
    return bool(parsed_destination and context_destination and parsed_destination == context_destination)


async def _load_plan(db_path: str) -> dict:
    raw = await get_preference(db_path, TRAVEL_PLAN_KEY)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}








async def _travel_budget_notes(db_path: str, request: str, plan: dict, template_mode: bool, preflight_context: str = "") -> str:
    topic = (
        "travel budget template with reusable categories and formulas"
        if template_mode
        else f"travel budget for {plan.get('destination', 'the trip')} from {plan.get('origin', 'Kuala Lumpur')}"
    )
    try:
        draft = await draft_markdown_with_gemini(
            db_path,
            (
                f"{topic}. User request: {request}. Keep notes focused on assumptions, budget categories, review points, and missing details."
                + (f"\n\nArtifact preflight blueprint:\n{preflight_context}" if preflight_context.strip() else "")
            ),
        )
    except Exception:
        return ""
    if not draft:
        return ""
    return _sanitize_budget_notes(_compact_note(draft.content), request, plan, template_mode)


def _compact_note(markdown: str) -> str:
    lines: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip().strip("# ")
        if not line or line.lower().startswith("sources"):
            continue
        if re.match(r"^\d+\)", line) or len(lines) < 4:
            lines.append(line)
        if len(" ".join(lines)) > 320:
            break
    return " ".join(lines)[:420]


def _sanitize_budget_notes(notes: str, request: str, plan: dict, template_mode: bool) -> str:
    destination = str(plan.get("destination") or "").strip()
    days = int(plan.get("days") or 0) if str(plan.get("days") or "").isdigit() else 0
    lowered = notes.lower()
    mentioned_days = [int(value) for value in re.findall(r"\b(\d{1,2})\s*[- ]?\s*day\b", lowered)]
    if template_mode:
        return notes if notes else "Reusable tracker for estimates, actual spend, variance, notes, and source links."
    if mentioned_days and (not days or any(value != days for value in mentioned_days)):
        return _default_budget_notes(destination, days)
    if any(marker in lowered for marker in ("expedition", "holy trinity", "current estimates")):
        return _default_budget_notes(destination, days)
    return notes or _default_budget_notes(destination, days)


def _default_budget_notes(destination: str, days: int) -> str:
    trip = f"{days}-day {destination} food trip" if days and destination else f"{destination} food trip" if destination else "food trip"
    return (
        f"Use this workbook to track the {trip} by restaurant, food item, estimate, actual spend, variance, source link, and suggestion. "
        "Keep flight and stay fields blank until selected, then update actual spending after each meal or purchase."
    )






































def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return text[:28] or "trip"


def _traveler_phrase(plan: dict) -> str:
    people = int(plan.get("people_count") or 1)
    return f"travel budget workbook for {people} traveler{'s' if people != 1 else ''}"
