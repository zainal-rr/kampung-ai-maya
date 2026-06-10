"""Excel document species: schema archetypes for the generic workbook lane.

The bespoke money lanes (travel budget, household budget, SaaS tracker,
Kampung AI cost) stay untouched. This module gives every OTHER spreadsheet a
species-appropriate column schema instead of forcing it into the shared
Task/Owner/Priority tracker or Section/Detail notes skeleton.

The model (Gemini) still writes the content; the species decides the shape.
Rows are filled from the drafted markdown sections, so wording stays
topic-specific while columns finally differ between a content calendar, a
research log, an inventory, a CRM list, and so on.
"""

from __future__ import annotations

# Topics that must stay in the bespoke money lanes regardless of other markers.
# Note: only real money words belong here. Product names like "kampung ai" must
# NOT block species ("Kampung AI YouTube content calendar" is a content
# calendar); the bespoke Kampung AI cost lane is selected upstream and its
# topics always contain "cost" or "budget" anyway.
_MONEY_MARKERS = ("budget", "expense", "spend", "cost", "saas", "invoice", "payroll")

# species -> trigger phrases (checked as substrings of the lowered topic)
_SPECIES_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Markers are multiword on purpose: short tokens like "roa" or "npl"
    # substring-match into "road" and "unplanned".
    ("financial_model", (
        "liquidity gap", "liquidity analysis", "cash flow analysis",
        "financial model", "financial analysis", "ratio analysis",
        "balance sheet", "loan book", "return on assets", "solvency",
        "capital adequacy", "preference share", "stress test",
        "income statement", "cash conversion", "non-performing",
    )),
    ("content_calendar", (
        "youtube", "content calendar", "content plan", "video", "channel",
        "editorial", "instagram", "tiktok", "blog", "podcast", "posting schedule",
    )),
    ("operations_log", (
        "farm", "agriculture", "crop", "livestock", "harvest", "plantation",
        "maintenance log", "operations log", "site log",
    )),
    ("research_log", (
        "research log", "study log", "experiment", "literature", "reading log",
        "study tracker", "lab notebook",
    )),
    ("habit_log", (
        "habit", "daily routine", "streak", "workout log", "exercise log",
        "fitness log",
    )),
    ("inventory", (
        "inventory", "stock list", "equipment list", "asset list", "stocktake",
        "tool list",
    )),
    ("crm_list", (
        "client list", "clients", "lead list", "leads", "customer list",
        "contact list", "crm", "outreach",
    )),
    ("dev_tracker", (
        "coding", "sprint", "developer", "bug tracker", "issue tracker",
        "repo", "software", "feature backlog", "dev tracker", "pull request",
    )),
    ("project_plan", (
        "project plan", "milestone", "gantt", "phase plan", "delivery plan",
        "launch plan",
    )),
    ("schedule", (
        "roster", "timetable", "shift schedule", "class schedule",
        "weekly schedule", "duty schedule",
    )),
)

_SCHEMAS: dict[str, list[str]] = {
    "financial_model": [
        "Line Item", "Category", "Time Bucket", "Inflow",
        "Outflow", "Net", "Cumulative Net", "Notes",
    ],
    "content_calendar": [
        "Week Or Date", "Title Or Topic", "Format", "Audience Hook",
        "Status", "Owner", "CTA Or Goal", "Notes",
    ],
    "operations_log": [
        "Date", "Area Or Asset", "Task", "Inputs Used",
        "Output Or Result", "Status", "Next Action",
    ],
    "research_log": [
        "Date", "Source Or Experiment", "Question", "Method",
        "Key Finding", "Confidence", "Follow Up",
    ],
    "habit_log": [
        "Habit", "Why It Matters", "Target Frequency", "Cue Or Time",
        "Current Streak", "Status", "Notes",
    ],
    "inventory": [
        "Item", "Category", "Location", "Quantity",
        "Unit Value", "Total Value", "Reorder Level", "Notes",
    ],
    "crm_list": [
        "Name", "Organization", "Role", "Status",
        "Last Contact", "Next Action", "Potential Value", "Notes",
    ],
    "dev_tracker": [
        "Item Or Ticket", "Type", "Module Or Repo", "Priority",
        "Status", "Estimate", "Blocker", "Next Action",
    ],
    "project_plan": [
        "Phase", "Milestone", "Owner", "Start", "End",
        "Status", "Dependency", "Notes",
    ],
    "schedule": [
        "Day", "Time", "Activity", "Location", "Owner", "Notes",
    ],
}

# For each species: (category_column_index, detail_column_index, defaults)
_FILL_PLAN: dict[str, tuple[int, int, dict[int, str]]] = {
    "financial_model": (1, 0, {2: "0-3 months"}),
    "content_calendar": (0, 1, {2: "To decide", 4: "Idea", 5: "Owner TBD"}),
    "operations_log": (1, 2, {5: "Planned"}),
    "research_log": (1, 4, {5: "Draft", 6: "Verify before relying on this."}),
    "habit_log": (0, 1, {5: "Not started"}),
    "inventory": (1, 0, {3: "1"}),
    "crm_list": (1, 0, {3: "New"}),
    "dev_tracker": (2, 0, {1: "Task", 3: "Medium", 4: "Not started"}),
    "project_plan": (0, 1, {5: "Not started"}),
    "schedule": (0, 2, {}),
}


def detect_excel_species(topic: str) -> str | None:
    lowered = " ".join(str(topic).lower().split())
    if any(marker in lowered for marker in _MONEY_MARKERS):
        return None
    for species, markers in _SPECIES_MARKERS:
        if any(marker in lowered for marker in markers):
            return species
    return None


def species_rows(
    species: str,
    topic: str,
    sections: list[tuple[str, list[str]]],
) -> tuple[list[str], list[list[str]]]:
    """Map drafted markdown sections into the species schema."""
    headers = _SCHEMAS[species]
    category_idx, detail_idx, defaults = _FILL_PLAN[species]
    width = len(headers)
    rows: list[list[str]] = []
    for heading, lines in sections:
        if heading.lower() in {"sources", "official sources", "third party sources"}:
            continue
        for line in lines[:4]:
            row = [""] * width
            row[category_idx] = heading
            row[detail_idx] = line
            for idx, value in defaults.items():
                row[idx] = value
            rows.append(row)
    if not rows:
        row = [""] * width
        row[category_idx] = "Starter"
        row[detail_idx] = f"Add the first {headers[detail_idx].lower()} for {topic}."
        rows.append(row)
    rows = rows[:30]
    if species == "inventory":
        rows = _with_inventory_formulas(rows, width)
    if species == "financial_model":
        rows = _with_financial_formulas(rows, width)
    return headers, rows


def _with_financial_formulas(rows: list[list[str]], width: int) -> list[list[str]]:
    """Per-row Net (=Inflow-Outflow) and running Cumulative Net, then a gap row
    with totals and a coverage ratio row. Data starts at row 4 (styled header
    convention). Amounts stay editable; formulas do the analysis."""
    first_row = 4
    for index, row in enumerate(rows):
        row_num = first_row + index
        row[5] = f'=IF(AND(D{row_num}="",E{row_num}=""),"",N(D{row_num})-N(E{row_num}))'
        if index == 0:
            row[6] = f"=F{row_num}"
        else:
            row[6] = f'=IF(F{row_num}="","",N(G{row_num - 1})+F{row_num})'
    total_row = first_row + len(rows)
    gap = [""] * width
    gap[0] = "Net position (gap if negative)"
    gap[1] = "Total"
    gap[3] = f"=SUM(D{first_row}:D{total_row - 1})"
    gap[4] = f"=SUM(E{first_row}:E{total_row - 1})"
    gap[5] = f"=D{total_row}-E{total_row}"
    gap[7] = "Negative net means obligations exceed expected inflows."
    coverage = [""] * width
    coverage[0] = "Coverage ratio (inflows / outflows)"
    coverage[1] = "Ratio"
    coverage[5] = f'=IF(N(E{total_row})=0,"",D{total_row}/E{total_row})'
    coverage[7] = "Below 1.0 means a funding gap; verify timing buckets, not just totals."
    return [*rows, gap, coverage]


def _with_inventory_formulas(rows: list[list[str]], width: int) -> list[list[str]]:
    """Quantity * Unit Value per row, plus a SUM total row (data starts row 4)."""
    first_row = 4
    for index, row in enumerate(rows):
        row_num = first_row + index
        row[5] = f'=IF(OR(D{row_num}="",E{row_num}=""),"",D{row_num}*E{row_num})'
    total_row = first_row + len(rows)
    total = [""] * width
    total[0] = "Total"
    total[5] = f"=SUM(F{first_row}:F{total_row - 1})"
    total[7] = "Formula row for total inventory value."
    return [*rows, total]
