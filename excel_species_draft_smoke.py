"""Deterministic smoke for the Excel species drafting contract.

Pins the fix for the 2026-06-11 live failure: species columns were right but
Gemini prose was mapped into cells, producing "spec documents masquerading as
spreadsheets". Contract: structured table in, validated rows out, seeds when
the draft is prose — never narrative in cells.
"""

from __future__ import annotations

from excel_species import _SCHEMAS, species_rows_structured
from excel_species_draft import (
    FINANCIAL_BUCKETS,
    excel_species_prompt_context,
    rows_from_species_draft,
    seed_rows,
)
from office_drafter import spreadsheet_from_markdown


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# The live failure mode, verbatim shape: a proposal document, not data.
PROSE_DRAFT = (
    "# YouTube Tracker Proposal\n\n"
    "## Executive Summary\nThis tracker uses a three-sheet system for your channel.\n\n"
    "## Objective\nTrack content across a dashboard and two more sheets.\n\n"
    "## Scope\nSheet 2 will contain metrics. Sheet 3 will contain ideas.\n\n"
    "## Next Steps\nReview the dashboard weekly.\n"
)

GOOD_CALENDAR_DRAFT = (
    "| Week Or Date | Title Or Topic | Format | Audience Hook | Status | Owner | CTA Or Goal | Notes |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
    "| Week 1 | Why VRF design fails | Video | The mistake in every lab | Idea | Zainal | Subscribe | |\n"
    "| Week 1 | Lab tour short | Short | 60 second rack tour | Idea | Zainal | Follow | |\n"
    "| Week 2 | OSPF vs BGP explained | Video | One diagram, no jargon | Scripted | Zainal | Comment | |\n"
    "| Week 2 | Config one-liner | Short | Copy this command | Idea | Zainal | Share | |\n"
    "| Week 3 | Live Q&A | Live | Bring lab questions | Idea | Zainal | Join | |\n"
    "| Week 4 | Month results | Video | What flopped | Idea | Zainal | Subscribe | |\n"
)

GOOD_FINANCIAL_DRAFT = (
    "| Line Item | Category | Time Bucket | Inflow | Outflow | Net | Cumulative Net | Notes |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
    "| Loan collections | Inflow | 0-1 months | 12 | | =SUM(bad) | | on-time portion |\n"
    "| Loan collections | Inflow | 1-3 months | 18 | | | | |\n"
    "| Delayed recoveries | Inflow | 3-6 months | 20 | | | | haircut applied |\n"
    "| Debt service | Outflow | 0-1 months | | 25 | | | |\n"
    "| Debt service | Outflow | 1-3 months | | 35 | | | |\n"
    "| Operating costs | Outflow | 0-1 months | | 6 | | | |\n"
)


def _contract_checks() -> None:
    for species in ("content_calendar", "dev_tracker", "financial_model"):
        contract = excel_species_prompt_context(species, "test topic")
        header_line = f"| {' | '.join(_SCHEMAS[species])} |"
        _require(header_line in contract, f"{species} contract must pin the exact header")
        _require("ONE markdown table" in contract, f"{species} contract must demand a single table")
        _require("No prose" in contract or "DATA ONLY" in contract, f"{species} contract must ban prose")
    fin = excel_species_prompt_context("financial_model", "liquidity")
    _require(all(bucket in fin for bucket in FINANCIAL_BUCKETS), "financial contract must list allowed buckets")


def _parser_checks() -> None:
    # Prose draft (the live failure) must be rejected outright.
    _require(rows_from_species_draft("content_calendar", PROSE_DRAFT) is None, "prose draft must parse to None")
    # Good table parses, preserving drafted values.
    rows = rows_from_species_draft("content_calendar", GOOD_CALENDAR_DRAFT)
    _require(rows is not None and len(rows) == 6, f"calendar draft should yield 6 rows: {rows and len(rows)}")
    _require(rows[0][1] == "Why VRF design fails", f"drafted title must survive: {rows[0]}")
    # Financial: buckets kept, formula-as-text stripped, Net column cleared.
    fin_rows = rows_from_species_draft("financial_model", GOOD_FINANCIAL_DRAFT)
    _require(fin_rows is not None and len(fin_rows) == 6, "financial draft should yield 6 rows")
    _require(fin_rows[1][2] == "1-3 months", f"drafted bucket must be kept: {fin_rows[1]}")
    _require(fin_rows[0][5] == "", "text formulas must be stripped from draft cells")


def _assembly_checks() -> None:
    # Drafted financial rows keep their buckets; formulas are rebuilt.
    fin_rows = rows_from_species_draft("financial_model", GOOD_FINANCIAL_DRAFT)
    headers, assembled = species_rows_structured("financial_model", "liquidity gap analysis", fin_rows)
    _require(headers == _SCHEMAS["financial_model"], "headers must match schema")
    buckets = {row[2] for row in assembled[:6]}
    _require(len(buckets) >= 3, f"drafted buckets must not collapse to one: {buckets}")
    joined = " ".join(str(cell) for row in assembled for cell in row)
    _require("=SUM(" in joined and "Coverage ratio" in joined, "gap and coverage formula rows must exist")
    _require("=IF(AND(D4" in str(assembled[0][5]), "per-row Net formula must be rebuilt")

    # Seeds are usable and narrative-free for every species with a seed set.
    for species in ("content_calendar", "operations_log", "dev_tracker", "financial_model"):
        seeded = seed_rows(species)
        _require(len(seeded) >= 5, f"{species} seeds too small")
        joined = " ".join(" ".join(row) for row in seeded).lower()
        _require("executive summary" not in joined and "dashboard" not in joined, f"{species} seeds must be data")
    fin_seed_buckets = {row[2] for row in seed_rows("financial_model")}
    _require(len(fin_seed_buckets) >= 3, f"financial seeds must vary buckets: {fin_seed_buckets}")


def _integration_checks() -> None:
    # End to end through the builder entry point used by the live flow.
    headers, rows = spreadsheet_from_markdown("make a youtube tracker for my channel", PROSE_DRAFT)
    _require(headers[0] == "Week Or Date", "species schema must hold")
    joined = " ".join(str(cell) for row in rows for cell in row).lower()
    for marker in ("executive summary", "objective", "scope", "three-sheet", "dashboard"):
        _require(marker not in joined, f"prose marker {marker!r} leaked into cells")
    headers2, rows2 = spreadsheet_from_markdown("make a youtube tracker for my channel", GOOD_CALENDAR_DRAFT)
    _require(any("Why VRF design fails" in str(cell) for row in rows2 for cell in row), "good draft rows must be used")
    # Non-species topics keep their existing lanes untouched.
    headers3, _rows3 = spreadsheet_from_markdown("compare router A and router B", "## Cost\ncheap\n## Setup\nfast")
    _require(headers3[0] == "Criteria", "comparison lane must be unchanged")


def main() -> None:
    _contract_checks()
    _parser_checks()
    _assembly_checks()
    _integration_checks()
    print("excel_species_draft_smoke: ok")


if __name__ == "__main__":
    main()
