from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from travel_budget_food import _food_restaurant_section
from travel_budget_style import _add_table, _style_sheet, _yes_no_validation


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
    title = "Travel Budget Template" if template_mode else f"{plan.get('destination', 'Trip')} Budget Tracker"
    ws.append([title, "", "", "", "", "", "", "", "", ""])
    ws.append(["Destination", plan.get("destination", ""), "Origin", plan.get("origin", ""), "Base currency", "MYR", "Foreign currency", "", "Exchange rate to MYR", 1])
    ws.append(["Travelers", people, "People source", plan.get("people_source", party.source), "Departure", plan.get("departure_date", ""), "Return", plan.get("return_date", "")])
    ws.append(["Flight choice", plan.get("flight_preference", ""), "Stay type", plan.get("accommodation_type", ""), "Preference", plan.get("accommodation_preference", ""), "", "", ""])
    ws.append(["Trip notes", plan.get("gemini_notes", ""), "", "", "", "", "", "", "", ""])
    ws.append([])

    ws.append(["Budget Snapshot", "", "", "", "", "", "", ""])
    ws.append(["Category", "Estimated Cost MYR", "Actual Cost MYR", "Variance MYR", "Notes", "", "", ""])
    snapshot_table_header = ws.max_row
    snapshot_first = ws.max_row + 1
    flight_total_cell = "I17"
    stay_total_cell = "G21"
    daily_total_range = "G25:G38"
    food_total_range = "D43:D49"
    food_actual_range = "E43:E49"
    ws.append(["Flights", f"={flight_total_cell}", "", f'=IF(OR(B{snapshot_first}="",C{snapshot_first}=""),"",C{snapshot_first}-B{snapshot_first})', "Selected flight only", "", "", ""])
    ws.append(["Accommodation", f"={stay_total_cell}", "", f'=IF(OR(B{snapshot_first + 1}="",C{snapshot_first + 1}=""),"",C{snapshot_first + 1}-B{snapshot_first + 1})', "Selected hotel or Airbnb only", "", "", ""])
    ws.append(["Food and restaurants", f"=SUM({food_total_range})", f"=SUM({food_actual_range})", f'=IF(OR(B{snapshot_first + 2}="",C{snapshot_first + 2}=""),"",C{snapshot_first + 2}-B{snapshot_first + 2})', "Food-trip restaurant detail", "", "", ""])
    ws.append(["Transport, activities, shopping", f"=SUM({daily_total_range})", "", f'=IF(OR(B{snapshot_first + 3}="",C{snapshot_first + 3}=""),"",C{snapshot_first + 3}-B{snapshot_first + 3})', "Daily non-food trip budget detail", "", "", ""])
    ws.append(["Buffer", "", "", f'=IF(OR(B{snapshot_first + 4}="",C{snapshot_first + 4}=""),"",C{snapshot_first + 4}-B{snapshot_first + 4})', "Optional extra cushion", "", "", ""])
    total_row = ws.max_row + 1
    ws.append(["Trip total", f"=SUM(B{snapshot_first}:B{total_row - 1})", f"=SUM(C{snapshot_first}:C{total_row - 1})", f"=SUM(D{snapshot_first}:D{total_row - 1})", "Total estimated, actual, and variance", "", "Per traveler estimate", f'=IF($B$3>0,B{total_row}/$B$3,"")'])
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
    active_days = 14 if template_mode else max(1, min(14, int(plan.get("days") or (2 if plan.get("food_focus") else 7))))
    for idx in range(1, 15):
        row_num = ws.max_row + 1
        label = f"Day {idx}" if template_mode or idx <= active_days else ""
        city = plan.get("destination", "") if not template_mode and idx <= active_days else ""
        ws.append([label, city, "", "", "", "", f"=SUM(C{row_num}:F{row_num})", ""])
    daily_end = ws.max_row
    _add_table(ws, "DailyBudget", f"A{daily_table_header}:H{daily_end}")
    ws.append([])

    food_start, food_end = _food_restaurant_section(ws, plan, template_mode)
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
