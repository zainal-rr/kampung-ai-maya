from __future__ import annotations

from document_actions_context import *


def _quick_request(topic: str) -> bool:
    low = topic.lower()
    return any(word in low for word in ("quick", "rough", "starter", "simple", "just draft"))


def _should_defer_html_app_to_artisan(text: str) -> bool:
    lowered = " ".join(str(text).lower().split())
    if any(marker in lowered for marker in ("html file", "single html", "one html", "self contained html", "self-contained html")):
        return False
    return any(marker in lowered for marker in (" app", "web app", "planner", "tracker", "dashboard", "ui"))


def _strip_quality_words(topic: str) -> str:
    return re.sub(r"\b(quick|rough|starter|simple|just draft)\b", " ", topic, flags=re.I).strip(" .") or topic


def _kampung_ai_cost_topic(topic: str) -> bool:
    low = topic.lower()
    return "kampung ai" in low and any(word in low for word in ("cost", "budget", "spend", "usage", "tracker"))


def _excel_lane(topic: str) -> str:
    if _kampung_ai_cost_topic(topic):
        return "Local Kampung AI cost tracker"
    if is_kampung_ai_testing_comparison(topic):
        return "Local Kampung AI testing comparison"
    return "Gemini Flash role-based spreadsheet draft"


def _internal_excel_topic(topic: str) -> bool:
    return _kampung_ai_cost_topic(topic) or is_kampung_ai_testing_comparison(topic)


def _prefixed_lane(lane: str, preflight: ArtifactPreflight | None) -> str:
    return f"{preflight.lane_prefix} + {lane}" if preflight else lane


def _budget_topic(topic: str) -> bool:
    low = topic.lower()
    budget_markers = ("budget", "budgeting", "expense", "cost", "spend", "spending", "tracker", "trip")
    food_markers = ("food", "restaurant", "restaurants", "meal", "meals", "mill", "mills", "mail", "mails", "dining", "cafe", "cafes")
    return any(word in low for word in budget_markers) or any(word in low for word in food_markers)


def _travel_budget_topic(topic: str) -> bool:
    low = topic.lower()
    destination_marker = any(word in low for word in ("seoul", "tokyo", "kyoto", "osaka", "bangkok", "singapore", "taipei", "hong kong"))
    duration_marker = bool(re.search(r"\b(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*[- ]?\s*days?\b", low))
    travel_marker = destination_marker or duration_marker or any(word in low for word in ("travel", "trip", "holiday", "vacation", "flight", "hotel", "airbnb"))
    food_marker = any(word in low for word in ("food", "restaurant", "restaurants", "meal", "meals", "mill", "mills", "mail", "mails", "dining", "cafe", "cafes"))
    budget_marker = any(word in low for word in ("budget", "budgeting", "expense", "cost", "spend", "spending", "tracker"))
    return (budget_marker and (travel_marker or food_marker)) or (food_marker and travel_marker)


def _task_tracker_topic(topic: str) -> bool:
    lowered = topic.lower()
    if any(word in lowered for word in ("budget", "expense", "cost", "variance", "spend")):
        return False
    tracker_marker = any(word in lowered for word in ("task tracker", "work tracker", "status tracker", "tracking sheet", "tracker"))
    office_marker = any(word in lowered for word in ("office", "work", "team", "project", "owner", "due date", "status", "priority"))
    return tracker_marker and office_marker


def _task_tracker_rows(topic: str) -> tuple[list[str], list[list[str]]]:
    lowered = topic.lower()
    title_prefix = "Office" if "office" in lowered or "work" in lowered else "Project"
    rows = [
        ["Prepare weekly operations update", "Owner TBD", "Date TBD", "Not Started", "High", "Collect input before Friday."],
        ["Confirm budget review inputs", "Owner TBD", "Date TBD", "Not Started", "High", "Ask owner to add source numbers."],
        ["Follow up pending approvals", "Owner TBD", "Date TBD", "In Progress", "Medium", "Track blockers and decision owner."],
        ["Review supplier delivery status", "Owner TBD", "Date TBD", "Not Started", "Medium", "Update once delivery date is confirmed."],
        ["Send Friday priority summary", "Owner TBD", "Date TBD", "Not Started", "Low", "Keep summary concise for the team."],
    ]
    headers = ["Task", "Owner", "Due Date", "Status", "Priority", "Notes"]
    if "department" in lowered or "team" in lowered:
        headers.insert(1, "Team")
        rows = [[row[0], title_prefix, *row[1:]] for row in rows]
    return headers, rows


def _budget_rows(topic: str) -> tuple[list[str], list[list[str]]]:
    lowered = topic.lower()
    if any(word in lowered for word in ("household", "home", "monthly", "family")) and not _travel_budget_topic(topic):
        first_row = 4
        categories = [
            ("Housing", "Rent or mortgage", "Monthly", "Owner TBD", "Add due date and payment account manually."),
            ("Utilities", "Electricity, water, gas", "Monthly", "Owner TBD", "Track bill due dates and actuals."),
            ("Groceries", "Supermarket and household supplies", "Weekly", "Owner TBD", "Use actuals from receipts."),
            ("Transport", "Fuel, parking, tolls, public transit", "Monthly", "Owner TBD", "Separate commute from optional trips if needed."),
            ("Phone And Internet", "Mobile plans and broadband", "Monthly", "Owner TBD", "Check for duplicate subscriptions."),
            ("Insurance And Medical", "Insurance, clinic, pharmacy", "Monthly", "Owner TBD", "Keep sensitive policy numbers out of the sheet."),
            ("Subscriptions", "Streaming, cloud, apps, memberships", "Monthly", "Owner TBD", "Cancel unused recurring items."),
            ("Savings", "Emergency fund or sinking funds", "Monthly", "Owner TBD", "Treat savings as a planned category."),
            ("Dining And Leisure", "Restaurants, cafes, entertainment", "Monthly", "Owner TBD", "Set a cap before the month starts."),
            ("Buffer", "Unplanned household costs", "Monthly", "Owner TBD", "Use this instead of hiding overspend."),
        ]
        rows = []
        for idx, (category, item, frequency, owner, note) in enumerate(categories):
            row_num = first_row + idx
            rows.append([
                category,
                item,
                "",
                "",
                f'=IF(OR(D{row_num}="",C{row_num}=""),"",D{row_num}-C{row_num})',
                frequency,
                owner,
                note,
            ])
        total_row = first_row + len(rows)
        rows.append([
            "Total",
            "All household categories",
            f"=SUM(C{first_row}:C{total_row - 1})",
            f"=SUM(D{first_row}:D{total_row - 1})",
            f"=SUM(E{first_row}:E{total_row - 1})",
            "",
            "",
            "Formula row for monthly estimate, actual, and variance.",
        ])
        return ["Category", "Item", "Estimated MYR", "Actual MYR", "Variance MYR", "Frequency", "Owner", "Notes"], rows
    first_row = 4
    categories = [
        ("Flights", "Add fare after search"),
        ("Accommodation", "Split by city if needed"),
        ("Local Transport", "Trains, subway, buses, airport transfers"),
        ("Food", "Daily estimate"),
        ("Attractions", "Tickets and activities"),
        ("Shopping", "Optional"),
        ("Miscellaneous", "Buffer"),
    ]
    rows = [
        [
            category,
            "",
            "",
            "",
            f'=IF(OR(D{first_row + idx}="",C{first_row + idx}=""),"",D{first_row + idx}-C{first_row + idx})',
            "",
            "",
            f'=IF(OR(G{first_row + idx}="",F{first_row + idx}=""),"",G{first_row + idx}-F{first_row + idx})',
            note,
        ]
        for idx, (category, note) in enumerate(categories)
    ]
    total_row = first_row + len(rows)
    rows.append([
        "Total",
        "All categories",
        f"=SUM(C{first_row}:C{total_row - 1})",
        f"=SUM(D{first_row}:D{total_row - 1})",
        f"=SUM(E{first_row}:E{total_row - 1})",
        f"=SUM(F{first_row}:F{total_row - 1})",
        f"=SUM(G{first_row}:G{total_row - 1})",
        f"=SUM(H{first_row}:H{total_row - 1})",
        "Formula row",
    ])
    if "tokyo" in lowered:
        rows[0][1] = "Tokyo flights or train"
        rows[1][1] = "Tokyo stay"
        rows[2][1] = "Tokyo metro, IC card, airport transfer"
    return ["Category", "Item", "Estimated JPY", "Actual JPY", "Variance JPY", "Estimated MYR", "Actual MYR", "Variance MYR", "Notes"], rows


def _budget_filename_topic(topic: str) -> str:
    lowered = topic.lower()
    destination = _destination_from_topic(lowered)
    if destination:
        return f"{destination} budget tracker"
    return re.sub(r"\b(?:budget|budgeting|tracker|spreadsheet|sheet|excel|xlsx)\b", " ", topic, flags=re.I).strip() or "budget tracker"


def _budget_title(topic: str) -> str:
    destination = _destination_from_topic(topic.lower())
    return f"{destination.title()} Budget Tracker" if destination else "Budget Tracker"


def _destination_from_topic(lowered: str) -> str:
    match = re.search(r"\b(?:for|about|to|in)\s+([a-z][a-z\s]{1,40}?)(?:\s+from|\s+for\s+\d|\s+on\s+|\s+between\s+|$)", lowered)
    if not match:
        return ""
    candidate = re.sub(r"\b(?:a|an|the|trip|budget|tracker|spreadsheet|sheet|excel|xlsx)\b", " ", match.group(1))
    return " ".join(candidate.split())


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _html_content(raw: str, topic: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("html"):
            cleaned = cleaned[4:].strip()
    if "<html" in cleaned.lower() and "<!doctype" in cleaned.lower():
        return cleaned.rstrip() + "\n"
    title = topic.strip().title() or "Maya HTML App"
    escaped = _escape_html(cleaned)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"  <title>{_escape_html(title)}</title>\n"
        "  <style>\n"
        "    body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }\n"
        "    main { max-width: 760px; margin: auto; }\n"
        "    pre { white-space: pre-wrap; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        f"    <h1>{_escape_html(title)}</h1>\n"
        f"    <pre>{escaped}</pre>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _looks_like_html_app(content: str) -> bool:
    lowered = content.lower()
    if not all(marker in lowered for marker in ("<!doctype", "<html", "<style", "<script")):
        return False
    if "<pre>" in lowered and ("### " in content or "# " in content):
        return False
    interactive_markers = ("<button", "<input", "<select", "<textarea", "addeventlistener", "localstorage")
    return any(marker in lowered for marker in interactive_markers)


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _attach(message: str, path: Path, channel: str) -> str:
    return f"{message}\n[file:{path}]" if channel == "telegram" else message


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "spreadsheet"
    if suffix == ".pptx":
        return "presentation"
    if suffix == ".docx":
        return "document"
    if suffix == ".md":
        return "note"
    return "file"
