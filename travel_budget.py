from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from artifact_naming import named_artifact_path
from artifact_quality import extract_xlsx_text, review_artifact_quality, validate_xlsx_path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation

from created_file_opener import open_created_file
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from markdown_drafter import draft_markdown_with_gemini
from storage import get_preference, upsert_preference
from utils import OSBridge
from workspace_paths import workspace_dir


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


async def create_travel_budget_excel(db_path: str, request: str, bridge: OSBridge | None = None, channel: str = "imac") -> str:
    bridge = bridge or OSBridge()
    saved_plan = await _load_plan(db_path)
    plan = dict(saved_plan)
    parsed = _parse_plan_updates(request)
    if parsed:
        plan.update(parsed)
    party = await infer_travel_party(db_path)
    template_mode = _template_request(request) or not _trip_specific_request(request, parsed)
    if template_mode:
        plan = _template_plan()
    else:
        people_count = int(plan.get("people_count") or party.count)
        plan["people_count"] = people_count
        plan.setdefault("people_source", party.source)
        plan.setdefault("origin", "Kuala Lumpur")
        plan.setdefault("destination", "Osaka / Kyoto")
        plan.setdefault("departure_date", "2026-08-30")
        plan.setdefault("return_date", "")
        plan.setdefault("flight_preference", "not selected yet")
        plan.setdefault("accommodation_type", "not selected yet")
        plan.setdefault("accommodation_preference", "middle to high-end; hotel 4-5 star or Airbnb guest favourite")
        await upsert_preference(db_path, TRAVEL_PLAN_KEY, json.dumps(plan, ensure_ascii=False), source="travel")

    output_dir = workspace_dir("spreadsheets", create=True)
    if template_mode:
        path = named_artifact_path(output_dir, "travel-budget-template", "xlsx")
    else:
        path = named_artifact_path(output_dir, f"travel-budget-{_slug(plan.get('destination', 'trip'))}", "xlsx")
    plan["gemini_notes"] = await _travel_budget_notes(db_path, request, plan, template_mode)
    _build_workbook(path, plan, party)
    local_qa = validate_xlsx_path(path, request)
    review_qa = await review_artifact_quality(db_path, "xlsx", request, extract_xlsx_text(path))
    quality = local_qa.merge(review_qa)
    await record_structured_artifact(
        db_path,
        TRAVEL_BUDGET_RUN_ID,
        local_artifact("spreadsheet", str(path), f"Created editable travel budget workbook: {quality.summary}", "travel_budget"),
    )
    await upsert_preference(db_path, "maya_last_document_path", str(path), source="travel_budget")
    label = "travel budget template" if template_mode else _traveler_phrase(plan)
    if not quality.passed:
        issue = quality.short_issue_text()
        if channel != "imac":
            return f"I created an editable {label}, but QA found: {issue}. I’m keeping it as a draft.\n[file:{path}]"
        return f"I created an editable {label} at {path}, but QA found: {issue}. I’m keeping it as a draft."
    if channel != "imac":
        return f"Done. I created an editable {label}.\n[file:{path}]"
    try:
        opened = open_created_file(path, bridge, "Microsoft Excel")
        opened_text = f" I opened it in {opened}." if opened else " I opened it."
    except Exception as exc:
        opened_text = f" I created it, but could not open it: {exc}"
    return f"Done. I created an editable {label} at {path}.{opened_text}"


async def infer_travel_party(db_path: str) -> TravelParty:
    plan = await _load_plan(db_path)
    if plan.get("people_count"):
        return TravelParty(max(1, int(plan["people_count"])), "saved travel plan")
    return TravelParty(1, "default until traveler count is explicit")


async def _load_plan(db_path: str) -> dict:
    raw = await get_preference(db_path, TRAVEL_PLAN_KEY)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _parse_plan_updates(text: str) -> dict:
    lowered = text.lower()
    changes: dict[str, object] = {}
    people = re.search(r"\b(\d{1,2})\s+(?:people|person|persons|travellers|travelers|guests|adults)\b", lowered)
    if people:
        changes["people_count"] = max(1, min(20, int(people.group(1))))
        changes["people_source"] = "explicit user request"
    if "cheapest" in lowered:
        changes["flight_preference"] = "cheapest"
    elif any(word in lowered for word in ("morning", "early flight")):
        changes["flight_preference"] = "morning schedule"
    elif any(word in lowered for word in ("night", "evening", "late flight")):
        changes["flight_preference"] = "night schedule"
    elif "nonstop" in lowered or "direct flight" in lowered:
        changes["flight_preference"] = "nonstop/direct"
    if "hotel" in lowered or "booking.com" in lowered:
        changes["accommodation_type"] = "hotel via Booking.com"
    if "airbnb" in lowered:
        changes["accommodation_type"] = "Airbnb"
    if any(word in lowered for word in ("middle", "mid range", "mid-range", "high end", "high-end", "4 star", "5 star", "guest favourite", "guest favorite")):
        changes["accommodation_preference"] = "middle to high-end; hotel 4-5 star or Airbnb guest favourite"
    destination = re.search(r"\b(?:to|in|for)\s+([A-Z][A-Za-z ,/]{2,50})(?:\s+from|\s+on|\s+for|\s+with|$)", text)
    if destination:
        value = " ".join(destination.group(1).split()).strip(" .,")
        if not re.search(r"\b(excel|budget|sheet|flight|hotel|airbnb|trip)\b", value, re.I):
            changes["destination"] = value
    return changes


def _template_request(text: str) -> bool:
    low = text.lower()
    return "template" in low or "travel sheet" in low or "specifically for travelling" in low or "travel purposes" in low


async def _travel_budget_notes(db_path: str, request: str, plan: dict, template_mode: bool) -> str:
    topic = (
        "travel budget template with reusable categories and formulas"
        if template_mode
        else f"travel budget for {plan.get('destination', 'the trip')} from {plan.get('origin', 'Kuala Lumpur')}"
    )
    try:
        draft = await draft_markdown_with_gemini(
            db_path,
            f"{topic}. User request: {request}. Keep notes focused on assumptions, budget categories, review points, and missing details.",
        )
    except Exception:
        return ""
    if not draft:
        return ""
    return _compact_note(draft.content)


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


def _trip_specific_request(text: str, parsed: dict) -> bool:
    low = text.lower()
    explicit = (
        "this trip",
        "my trip",
        "our trip",
        "current trip",
        "for the trip",
        "for my travel",
        "for our travel",
        "use the trip",
        "use current",
    )
    if any(phrase in low for phrase in explicit):
        return True
    if parsed.get("destination") or parsed.get("departure_date") or parsed.get("return_date"):
        return True
    if re.search(r"\bto\s+[A-Z][A-Za-z ,/]{2,50}\b", text):
        return True
    return False


def _template_plan() -> dict:
    return {
        "origin": "",
        "destination": "",
        "departure_date": "",
        "return_date": "",
        "flight_preference": "",
        "accommodation_type": "",
        "accommodation_preference": "middle to high-end by default; hotels 4-5 star or Airbnb guest favourite when planning a real trip",
        "people_count": "",
        "people_source": "enter manually",
        "template_mode": True,
    }


def _plan_reply(plan: dict, changes: dict, party: TravelParty) -> str:
    lines = ["Travel plan memory updated."]
    if changes:
        lines.append("Saved:")
        lines.extend(f"- {key}: {value}" for key, value in changes.items())
    else:
        lines.append("No new parameter was detected, so I kept the existing plan.")
    lines.append(f"Travelers: {plan.get('people_count', party.count)} ({plan.get('people_source', party.source)})")
    if not plan.get("flight_preference"):
        lines.append("Next: Which flight should I keep: cheapest, morning schedule, night schedule, or a specific option?")
    elif not plan.get("accommodation_type"):
        lines.append("Next: Hotel on Booking.com or Airbnb?")
    return "\n".join(lines)


def _build_workbook(path: Path, plan: dict, party: TravelParty) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Travel Budget"
    _single_sheet_budget(sheet, plan, party)
    _style_sheet(sheet)
    wb.save(path)


def _single_sheet_budget(ws, plan: dict, party: TravelParty) -> None:
    template_mode = bool(plan.get("template_mode"))
    people = plan.get("people_count") if template_mode else int(plan.get("people_count") or party.count)
    title = "Travel Budget Template" if template_mode else "Maya Travel Budget"
    ws.append([title, "", "", "", "", "", "", "", "", ""])
    ws.append(["Destination", plan.get("destination", ""), "Origin", plan.get("origin", ""), "Base currency", "MYR", "Foreign currency", "", "Exchange rate to MYR", 1])
    ws.append(["Travelers", people, "People source", plan.get("people_source", party.source), "Departure", plan.get("departure_date", ""), "Return", plan.get("return_date", "")])
    ws.append(["Flight choice", plan.get("flight_preference", ""), "Stay type", plan.get("accommodation_type", ""), "Preference", plan.get("accommodation_preference", ""), "", "", ""])
    ws.append(["Trip notes", plan.get("gemini_notes", ""), "", "", "", "", "", "", "", ""])
    ws.append([])

    ws.append(["Budget Snapshot", "", "", "", "", "", "", ""])
    ws.append(["Item", "Estimated foreign", "Estimated MYR", "Actual MYR", "Notes", "", "", ""])
    snapshot_table_header = ws.max_row
    snapshot_first = ws.max_row + 1
    flight_total_cell = "I17"
    stay_total_cell = "G21"
    daily_total_range = "G25:G38"
    ws.append(["Flight", "", f"={flight_total_cell}", "", "Selected flight only", "", "", ""])
    ws.append(["Stay", "", f"={stay_total_cell}", "", "Selected hotel or Airbnb only", "", "", ""])
    ws.append(["Daily spend", "", f"=SUM({daily_total_range})", "", "Food, transport, activities and shopping", "", "", ""])
    ws.append(["Buffer", "", "", "", "Optional extra cushion", "", "", ""])
    total_row = ws.max_row + 1
    ws.append(["Trip total", f"=SUM(B{snapshot_first}:B{total_row - 1})", f"=SUM(C{snapshot_first}:C{total_row - 1})", f"=SUM(D{snapshot_first}:D{total_row - 1})", "", "", "Per traveler", f'=IF($B$3>0,C{total_row}/$B$3,"")'])
    _add_table(ws, "BudgetSnapshot", f"A{snapshot_table_header}:E{total_row}")
    ws.append([])

    ws.append(["Selected Flight", "", "", "", "", "", "", ""])
    ws.append(["Airline / option", "Route", "Depart", "Arrive", "Duration", "Stops", "Price per person MYR", "Travelers", "Total MYR", "Notes"])
    flight_table_header = ws.max_row
    flight_row = ws.max_row + 1
    ws.append([_selected_flight_label(plan), _route_label(plan), "", "", "", "", "", '=IF($B$3="","",$B$3)', f'=IF(OR(G{flight_row}="",H{flight_row}=""),"",G{flight_row}*H{flight_row})', "Enter selected flight details"])
    _add_table(ws, "SelectedFlight", f"A{flight_table_header}:J{flight_row}")
    ws.append([])

    ws.append(["Selected Stay", "", "", "", "", "", "", ""])
    ws.append(["Provider", "Name", "Area / Location", "Check-in", "Check-out", "Nights", "Total MYR", "Notes"])
    stay_table_header = ws.max_row
    stay_row = ws.max_row + 1
    ws.append([plan.get("accommodation_type", ""), "", "", "=F3", "=H3", "", "", "Enter accommodation details"])
    _add_table(ws, "SelectedStay", f"A{stay_table_header}:H{stay_row}")
    ws.append([])

    ws.append(["Daily Trip Budget", "", "", "", "", "", "", ""])
    ws.append(["Day", "City", "Food MYR", "Local transport MYR", "Activities MYR", "Shopping MYR", "Daily Total MYR", "Notes"])
    daily_table_header = ws.max_row
    daily_start = ws.max_row + 1
    for idx in range(1, 15):
        row_num = ws.max_row + 1
        ws.append([f"Day {idx}", "", "", "", "", "", f"=SUM(C{row_num}:F{row_num})", ""])
    daily_end = ws.max_row
    _add_table(ws, "DailyBudget", f"A{daily_table_header}:H{daily_end}")
    ws.append([])

    ws.append(["Actual Spending", "", "", "", "", "", "", ""])
    ws.append(["Date", "Category", "What", "City", "Paid by", "Amount MYR", "Running Total MYR", "Notes"])
    tracker_table_header = ws.max_row
    tracker_start = ws.max_row + 1
    for row in range(tracker_start, tracker_start + 40):
        ws.append(["", "", "", "", "", "", f'=IF(F{row}="", "", SUM($F${tracker_start}:F{row}))', ""])
    tracker_end = ws.max_row
    _add_table(ws, "ActualSpending", f"A{tracker_table_header}:H{tracker_end}")
    ws.append([])

    ws.append(["Assumptions", "", "", "", "", "", "", ""])
    ws.append(["Parameter", "Value", "Source / note", "", "", "", "", ""])
    if template_mode:
        assumptions = [
            ["Template use", "Reusable blank planner", "Fill only the rows you need"],
            ["Travelers", "Enter manually in B3", "Used for per-traveler total and flight total"],
            ["Currency", "MYR base, optional foreign currency", "Use J2 for exchange rate notes if needed"],
            ["Flight and stay", "Optional", "Use selected rows only after you choose options"],
            ["Safety", "Stop before payment/login/private details", "No card, passport, OTP, password, or final submit"],
        ]
    else:
        assumptions = [
            ["People count", people, plan.get("people_source", party.source)],
            ["Call participants", "not used for traveler count", "Maya must ask for explicit traveler count"],
            ["Flight choice", plan.get("flight_preference", "not selected yet"), "Saved after Maya asks you which flight to keep"],
            ["Accommodation", plan.get("accommodation_type", "not selected yet"), "Saved after Maya asks hotel or Airbnb"],
            ["Safety", "Stop before payment/login/private details", "No card, passport, OTP, password, or final submit"],
        ]
    for row in assumptions:
        ws.append(row + ["", "", "", "", ""])
    categories = "Flight,Accommodation,Food,Transport,Activities,Shopping,Misc"
    dv = DataValidation(type="list", formula1=f'"{categories}"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"B{tracker_start}:B{tracker_end}")


def _summary_sheet(ws, plan: dict, party: TravelParty) -> None:
    people = int(plan.get("people_count") or party.count)
    rows = [
        ["Maya Travel Budget", ""],
        ["Destination", plan.get("destination", "Osaka / Kyoto")],
        ["Origin", plan.get("origin", "Kuala Lumpur")],
        ["Departure date", plan.get("departure_date", "2026-08-30")],
        ["Return date", plan.get("return_date", "One way / not selected") or "One way / not selected"],
        ["Travelers", people],
        ["People source", plan.get("people_source", party.source)],
        ["Flight preference", plan.get("flight_preference", "not selected yet")],
        ["Accommodation type", plan.get("accommodation_type", "not selected yet")],
        ["Accommodation preference", plan.get("accommodation_preference", "middle to high-end; hotel 4-5 star or Airbnb guest favourite")],
        ["Selected flight total MYR", "=SUM('Flight Options'!J2:J20)"],
        ["Selected accommodation total MYR", "=SUM(Accommodation!K2:K20)"],
        ["Daily budget total MYR", "=SUM('Daily Budget'!F2:F40)"],
        ["Expense actual total MYR", "=SUM('Expense Tracker'!G2:G200)"],
        ["Estimated trip total MYR", "=B11+B12+B13"],
        ["Estimated per person MYR", "=IF(B6>0,B15/B6,\"\")"],
        ["Remaining vs estimate MYR", "=B15-B14"],
    ]
    for row in rows:
        ws.append(row)
    ws["A1"].font = Font(size=18, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="1F4E79")
    ws.merge_cells("A1:B1")


def _flight_sheet(ws, plan: dict) -> None:
    headers = ["Keep?", "Airline", "Depart", "Arrive", "Duration", "Stops", "Route", "Price MYR", "People", "Total MYR", "Notes"]
    ws.append(headers)
    rows = [
        ["Yes" if plan.get("flight_preference") == "cheapest" else "", "Cheapest option", "", "", "", "", "KUL-KIX", "", "=Summary!$B$6", '=IF(A2="Yes",H2*I2,0)', "Fill after Google Flights search"],
        ["", "Morning option", "", "", "", "", "KUL-KIX", "", "=Summary!$B$6", '=IF(A3="Yes",H3*I3,0)', ""],
        ["", "Night option", "", "", "", "", "KUL-KIX", "", "=Summary!$B$6", '=IF(A4="Yes",H4*I4,0)', ""],
        ["", "Preferred option", "", "", "", "", "KUL-KIX", "", "=Summary!$B$6", '=IF(A5="Yes",H5*I5,0)', ""],
    ]
    for row in rows:
        ws.append(row)
    _yes_no_validation(ws, "A2:A20")


def _stay_sheet(ws, plan: dict) -> None:
    headers = ["Keep?", "Provider", "Name", "Area / Location", "Rating / Class", "Guest favourite?", "Check-in", "Check-out", "Nightly MYR", "Nights", "Total MYR", "Notes"]
    ws.append(headers)
    provider = plan.get("accommodation_type", "Booking.com or Airbnb")
    rows = [
        ["", provider, "Middle range option", "", "4 star / guest favourite", "", "=Summary!$B$4", "=Summary!$B$5", "", 5, '=IF(A2="Yes",I2*J2,0)', "Prefer 4-5 star hotel or Airbnb guest favourite"],
        ["", provider, "High end option", "", "5 star / guest favourite", "", "=Summary!$B$4", "=Summary!$B$5", "", 5, '=IF(A3="Yes",I3*J3,0)', ""],
        ["", provider, "Backup option", "", "", "", "=Summary!$B$4", "=Summary!$B$5", "", 5, '=IF(A4="Yes",I4*J4,0)', ""],
    ]
    for row in rows:
        ws.append(row)
    _yes_no_validation(ws, "A2:A30")


def _daily_sheet(ws, plan: dict) -> None:
    headers = ["Date", "City", "Food MYR", "Local transport MYR", "Activities MYR", "Daily Total MYR", "Notes"]
    ws.append(headers)
    for idx in range(1, 8):
        row = [f"Day {idx}", "", "", "", "", f"=SUM(C{idx+1}:E{idx+1})", ""]
        ws.append(row)


def _tracker_sheet(ws) -> None:
    headers = ["Date", "Category", "Vendor / Item", "City", "Paid by", "Amount MYR", "Trip Total MYR", "Notes"]
    ws.append(headers)
    categories = "Flight,Accommodation,Food,Transport,Activities,Shopping,Misc"
    dv = DataValidation(type="list", formula1=f'"{categories}"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("B2:B200")
    for row in range(2, 202):
        ws[f"G{row}"] = f'=IF(F{row}="", "", SUM($F$2:F{row}))'


def _assumptions_sheet(ws, plan: dict, party: TravelParty) -> None:
    rows = [
        ["Parameter", "Value", "Source / note"],
        ["People count", plan.get("people_count", party.count), plan.get("people_source", party.source)],
        ["Call participants", "not used for traveler count", "Maya must ask for explicit traveler count"],
        ["Flight selection", plan.get("flight_preference", "not selected yet"), "Maya should ask cheapest / morning / night / specific option"],
        ["Accommodation", plan.get("accommodation_type", "not selected yet"), "Maya should ask hotel or Airbnb"],
        ["Accommodation preference", plan.get("accommodation_preference", ""), "Default: middle to high-end; hotels 4-5 star; Airbnb guest favourite"],
        ["Safety", "Stop before payment/login/private details", "Do not enter card, passport, OTP, password, or final booking submit"],
    ]
    for row in rows:
        ws.append(row)


def _style_sheet(ws) -> None:
    header_fill = PatternFill("solid", fgColor="DCEBFF")
    title_fill = PatternFill("solid", fgColor="234E70")
    section_fill = PatternFill("solid", fgColor="D9EAD3")
    soft_fill = PatternFill("solid", fgColor="F8FBFF")
    thin = Side(style="thin", color="CFD8E3")
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if cell.value in {"Budget Snapshot", "Selected Flight", "Selected Stay", "Daily Trip Budget", "Actual Spending", "Assumptions"}:
                cell.font = Font(bold=True, color="234E70")
                cell.fill = section_fill
            elif cell.row > 1:
                cell.fill = soft_fill
    if ws.max_row >= 1:
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
        if ws["A1"].value in {"Maya Travel Budget", "Travel Budget Template"}:
            ws["A1"].fill = title_fill
            ws["A1"].font = Font(size=18, bold=True, color="FFFFFF")
            try:
                ws.merge_cells("A1:J1")
            except ValueError:
                pass
    for row in (7, 15, 19, 23, 34, 55):
        if row <= ws.max_row:
            for cell in ws[row]:
                if cell.value:
                    cell.font = Font(bold=True, color="234E70")
                    cell.fill = header_fill
    for column in range(1, ws.max_column + 1):
        letter = get_column_letter(column)
        max_len = max(len(str(ws.cell(row=row, column=column).value or "")) for row in range(1, min(ws.max_row, 40) + 1))
        ws.column_dimensions[letter].width = min(max(max_len + 2, 11), 34)
    ws.freeze_panes = "A2"


def _yes_no_validation(ws, cell_range: str) -> None:
    dv = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(cell_range)


def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return text[:28] or "trip"


def _traveler_phrase(plan: dict) -> str:
    people = int(plan.get("people_count") or 1)
    return f"travel budget workbook for {people} traveler{'s' if people != 1 else ''}"


def _selected_flight_label(plan: dict) -> str:
    preference = str(plan.get("flight_preference") or "").strip()
    if not preference or preference == "not selected yet":
        return "Selected flight"
    return f"Selected flight: {preference}"


def _route_label(plan: dict) -> str:
    origin = str(plan.get("origin") or "").strip()
    destination = str(plan.get("destination") or "").strip()
    if origin and destination:
        return f"{origin} to {destination}"
    return ""


def _add_table(ws, name: str, ref: str) -> None:
    try:
        table = Table(displayName=name, ref=ref)
        style = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        table.tableStyleInfo = style
        ws.add_table(table)
    except ValueError:
        pass
