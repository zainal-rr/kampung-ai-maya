"""Excel species drafting contract: structured rows in, never prose-in-cells.

Live finding 2026-06-11 (`kampung-ai-phase-4-5-live-test-report`): the species
layer chose correct columns, but Gemini free-wrote proposal documents and the
builder mapped narrative paragraphs into spreadsheet rows. Every tracker
failed Claude review as "a spec masquerading as a spreadsheet".

Root cause: `markdown_drafter._prompt` rule 4 told the model to *describe*
"useful columns, rows, formulas" for spreadsheets. Description is exactly what
we got.

This module is the fix, in three parts:

1. `excel_species_prompt_context(species, topic)` — drafting instructions
   appended to the Gemini prompt: return ONE markdown table with EXACTLY the
   species columns, real row data, no prose, no sheet/dashboard claims.
2. `rows_from_species_draft(species, markdown)` — strict parser/validator:
   extracts the table, verifies the header matches the species schema, drops
   narrative rows, and returns None when the draft is not usable as data.
3. `seed_rows(species)` — deterministic, practical fallback rows per species,
   so a failed draft still produces a usable workbook (the monthly budget
   builder passed live for exactly this reason: deterministic content).

The builder never maps prose sections into cells for species topics again.
"""

from __future__ import annotations

import re

from excel_species import _SCHEMAS  # single source of truth for columns

FINANCIAL_BUCKETS = ("0-1 months", "1-3 months", "3-6 months", "6-12 months", "12+ months")

# A row containing any of these is narrative/spec content, not data.
NARRATIVE_ROW_MARKERS = (
    "executive summary", "objective", "scope", "overview", "introduction",
    "this tracker", "this workbook", "this spreadsheet", "the workbook",
    "sheet 2", "sheet two", "sheet 3", "second sheet", "third sheet",
    "three-sheet", "dashboard", "next steps", "sources", "recommendation",
    "purpose of", "how to use", "instructions",
)

MIN_DRAFT_ROWS = 5
MAX_ROWS = 30

_SPECIES_ROW_GUIDANCE = {
    "content_calendar": "Each row is one real planned post/video: concrete titles, varied formats (Video, Short, Live, Post), week or date labels, a real hook, and a status from Idea/Scripted/Filming/Editing/Published.",
    "operations_log": "Each row is one real farm/site operation: concrete areas or assets, specific tasks, actual inputs used, observable outputs, and a status from Planned/In progress/Done.",
    "research_log": "Each row is one real source or experiment: a named source, the question it addresses, the method, a one-line finding, and a confidence level.",
    "habit_log": "Each row is one real habit with why it matters, a measurable target frequency, and a concrete cue or time.",
    "inventory": "Each row is one real item with category, location, numeric quantity, and numeric unit value where known. Leave Total Value empty; formulas fill it.",
    "crm_list": "Each row is one real contact or lead archetype with organization, role, status from New/Contacted/Qualified/Won/Lost, and a concrete next action.",
    "dev_tracker": "Each row is one real ticket or task: short imperative title, Type from Task/Bug/Feature/Chore, module or repo area, priority, status, and an estimate like 2h or 3d.",
    "project_plan": "Each row is one real milestone with phase, owner role, start/end labels, status, and dependency.",
    "schedule": "Each row is one real schedule slot with day, time range, activity, and location.",
    "financial_model": (
        "Each row is one real liquidity line item (for example: Loan collections, Asset sale proceeds, "
        "Debt service, Operating costs, Committed disbursements). Category is exactly Inflow or Outflow. "
        f"Time Bucket must be one of: {', '.join(FINANCIAL_BUCKETS)} — vary buckets across rows, never put every row in one bucket. "
        "Inflow/Outflow cells contain plain numbers or stay empty for the user. Leave Net and Cumulative Net EMPTY; formulas fill them."
    ),
}


def excel_species_prompt_context(species: str, topic: str) -> str:
    """Drafting contract appended to the Gemini prompt for species topics."""
    headers = _SCHEMAS[species]
    guidance = _SPECIES_ROW_GUIDANCE.get(species, "Each row is one real, concrete entry.")
    return (
        "SPREADSHEET DATA CONTRACT (overrides any document-section standard above):\n"
        f"This request builds a spreadsheet of species '{species}'. Return ONE markdown table and nothing else.\n"
        f"1) The header row must be exactly: | {' | '.join(headers)} |\n"
        f"2) Provide 8 to 14 data rows. {guidance}\n"
        "3) Rows contain DATA ONLY. No prose paragraphs, no section headings, no explanation rows, "
        "no rows about the tracker itself, no 'Executive Summary' or 'Next Steps' rows.\n"
        "4) Do not mention or promise other sheets, tabs, or dashboards. One table is the deliverable.\n"
        "5) Do not write formulas as text; leave computed columns empty.\n"
        "6) No text before or after the table. No Sources section."
    )


def rows_from_species_draft(species: str, markdown: str) -> list[list[str]] | None:
    """Parse the drafted markdown into validated species rows.

    Returns None when the draft cannot be trusted as data (wrong/missing
    header, too few rows, or mostly narrative) — the caller then uses
    deterministic seed rows instead of ever mapping prose into cells.
    """
    headers = _SCHEMAS[species]
    table = _first_markdown_table(markdown)
    if not table:
        return None
    header_cells, data_rows = table
    if not _header_matches(header_cells, headers):
        return None
    width = len(headers)
    clean: list[list[str]] = []
    dropped = 0
    for cells in data_rows:
        row = [_clean_cell(cell) for cell in cells[:width]]
        row += [""] * (width - len(row))
        joined = " ".join(row).lower()
        if not any(cell for cell in row):
            continue
        if any(marker in joined for marker in NARRATIVE_ROW_MARKERS):
            dropped += 1
            continue
        if species == "financial_model":
            row = _normalize_financial_row(row, headers)
        clean.append(row)
        if len(clean) >= MAX_ROWS:
            break
    if len(clean) < MIN_DRAFT_ROWS:
        return None
    if dropped > len(clean):
        # More narrative than data: the draft is a document, not a dataset.
        return None
    return clean


def seed_rows(species: str) -> list[list[str]]:
    """Deterministic, practical fallback rows per species. Always usable."""
    seeds = _SEED_ROWS.get(species)
    if seeds:
        return [list(row) for row in seeds]
    width = len(_SCHEMAS[species])
    return [["Starter entry"] + [""] * (width - 1) for _ in range(MIN_DRAFT_ROWS)]


def _first_markdown_table(markdown: str) -> tuple[list[str], list[list[str]]] | None:
    lines = [line.strip() for line in str(markdown).splitlines()]
    table_lines = [line for line in lines if line.startswith("|") and line.endswith("|") and line.count("|") >= 3]
    if len(table_lines) < 3:
        return None
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in table_lines]
    header = rows[0]
    body = [row for row in rows[1:] if not _is_separator_row(row)]
    return header, body


def _is_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", cell.strip()) is not None for cell in cells if cell.strip()) and any(cells)


def _header_matches(found: list[str], expected: list[str]) -> bool:
    if len(found) != len(expected):
        return False
    normalize = lambda text: re.sub(r"[^a-z0-9]+", "", str(text).lower())
    matches = sum(1 for f, e in zip(found, expected) if normalize(f) == normalize(e))
    return matches >= max(2, int(0.7 * len(expected)))


def _clean_cell(cell: str) -> str:
    text = re.sub(r"\*\*|__|`", "", str(cell)).strip()
    # A formula written as text in a non-formula draft cell is a lie; drop it.
    if text.startswith("="):
        return ""
    return text[:200]


def _normalize_financial_row(row: list[str], headers: list[str]) -> list[str]:
    bucket_idx = headers.index("Time Bucket")
    net_idx = headers.index("Net")
    cumulative_idx = headers.index("Cumulative Net")
    category_idx = headers.index("Category")
    bucket = row[bucket_idx].strip()
    if bucket and bucket not in FINANCIAL_BUCKETS:
        matched = next((b for b in FINANCIAL_BUCKETS if b.split()[0] in bucket), "")
        row[bucket_idx] = matched
    category = row[category_idx].strip().title()
    row[category_idx] = category if category in {"Inflow", "Outflow", "Total", "Ratio"} else ("Inflow" if "in" in category.lower() else "Outflow")
    row[net_idx] = ""        # formulas own these
    row[cumulative_idx] = ""
    return row


_SEED_ROWS: dict[str, tuple[tuple[str, ...], ...]] = {
    "content_calendar": (
        ("Week 1", "Channel introduction: who this is for", "Video", "The one problem this channel solves", "Idea", "Owner TBD", "Subscribe", "Replace with your real plan"),
        ("Week 1", "Behind the scenes setup short", "Short", "60-second tour of the setup", "Idea", "Owner TBD", "Follow", ""),
        ("Week 2", "Deep dive on the core topic", "Video", "The mistake most beginners make", "Scripted", "Owner TBD", "Comment", ""),
        ("Week 2", "Quick tip from the deep dive", "Short", "One tip in 30 seconds", "Idea", "Owner TBD", "Share", ""),
        ("Week 3", "Live Q&A with early viewers", "Live", "Bring your questions", "Idea", "Owner TBD", "Join live", ""),
        ("Week 4", "Results and lessons after one month", "Video", "What worked and what flopped", "Idea", "Owner TBD", "Subscribe", ""),
    ),
    "operations_log": (
        ("Week 1", "North field", "Soil preparation", "Compost, tiller", "Beds ready for planting", "Planned", "Schedule planting"),
        ("Week 1", "Irrigation line", "Leak inspection", "Spare fittings", "Two joints replaced", "Planned", "Re-test pressure"),
        ("Week 2", "North field", "Planting", "Seedlings, starter fertilizer", "Rows planted", "Planned", "First watering schedule"),
        ("Week 2", "Equipment shed", "Tractor service", "Oil, filter", "Service complete", "Planned", "Log next service date"),
        ("Week 3", "South field", "Pest scouting", "Traps", "Counts recorded", "Planned", "Decide on treatment"),
        ("Week 4", "All fields", "Growth check", "Notebook, camera", "Photos and notes", "Planned", "Adjust fertilizer plan"),
    ),
    "dev_tracker": (
        ("Set up CI pipeline", "Chore", "tooling", "High", "Not started", "1d", "", "Define the test gate first"),
        ("Fix login session timeout bug", "Bug", "auth", "High", "Not started", "4h", "", "Reproduce with expired token"),
        ("Add input validation to signup form", "Task", "frontend", "Medium", "Not started", "3h", "", ""),
        ("Write API error handling guide", "Task", "docs", "Low", "Not started", "2h", "", ""),
        ("Refactor database connection pool", "Task", "backend", "Medium", "Not started", "1d", "Depends on CI", ""),
        ("Add smoke test for payment flow", "Task", "payments", "High", "Not started", "4h", "", ""),
    ),
    "financial_model": (
        ("Loan collections (on time)", "Inflow", "0-1 months", "", "", "", "", "Enter expected on-time collections"),
        ("Loan collections (on time)", "Inflow", "1-3 months", "", "", "", "", ""),
        ("Delayed collections recovered", "Inflow", "3-6 months", "", "", "", "", "Apply a haircut for re-delay"),
        ("Asset sale proceeds", "Inflow", "1-3 months", "", "", "", "", "Fire-sale value, not book value"),
        ("Debt service due", "Outflow", "0-1 months", "", "", "", "", ""),
        ("Debt service due", "Outflow", "1-3 months", "", "", "", "", ""),
        ("Operating costs", "Outflow", "0-1 months", "", "", "", "", ""),
        ("Committed disbursements", "Outflow", "1-3 months", "", "", "", "", "Freeze uncommitted lending first"),
    ),
}
