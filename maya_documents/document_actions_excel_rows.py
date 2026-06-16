from __future__ import annotations

import re


def _travel_budget_topic(topic: str) -> bool:
    low = topic.lower()
    destination_marker = any(word in low for word in ("seoul", "tokyo", "kyoto", "osaka", "bangkok", "singapore", "taipei", "hong kong"))
    duration_marker = bool(re.search(r"\b(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*[- ]?\s*days?\b", low))
    travel_marker = destination_marker or duration_marker or any(word in low for word in ("travel", "trip", "holiday", "vacation", "flight", "hotel", "airbnb"))
    food_marker = any(word in low for word in ("food", "restaurant", "restaurants", "meal", "meals", "mill", "mills", "mail", "mails", "dining", "cafe", "cafes"))
    budget_marker = any(word in low for word in ("budget", "budgeting", "expense", "cost", "spend", "spending", "tracker"))
    return (budget_marker and (travel_marker or food_marker)) or (food_marker and travel_marker)


def _task_tracker_rows(topic: str) -> tuple[list[str], list[list[str]]]:
    lowered = topic.lower()
    coding = any(word in lowered for word in ("coding", "browser skill", "sprint", "developer", "repo"))
    tasks = _coding_tasks() if coding else _office_tasks()
    first_row = 4
    rows = []
    for index, (task, priority, status, note) in enumerate(tasks):
        row_num = first_row + index
        rows.append([
            task,
            "Owner TBD",
            priority,
            status,
            "",
            "",
            f'=IF(OR(F{row_num}="",E{row_num}=""),"",F{row_num}-E{row_num})',
            "",
            note,
        ])
    total_row = first_row + len(rows)
    rows.append([
        "Total",
        "",
        "",
        "",
        f"=SUM(E{first_row}:E{total_row - 1})",
        f"=SUM(F{first_row}:F{total_row - 1})",
        f"=SUM(G{first_row}:G{total_row - 1})",
        "",
        "Formula row for estimated, actual, and variance hours.",
    ])
    return ["Task", "Owner", "Priority", "Status", "Estimate Hours", "Actual Hours", "Variance Hours", "Blocker", "Next Action"], rows


def _saas_tracker_rows(topic: str) -> tuple[list[str], list[list[str]]]:
    first_row = 4
    rows = []
    for index, (provider, tool, owner, plan, note) in enumerate(_saas_tools()):
        row_num = first_row + index
        rows.append([
            provider,
            tool,
            owner,
            plan,
            "",
            "",
            f'=IF(OR(F{row_num}="",E{row_num}=""),"",F{row_num}-E{row_num})',
            "",
            "",
            note,
        ])
    total_row = first_row + len(rows)
    rows.append([
        "Total",
        "All SaaS tools",
        "",
        "",
        f"=SUM(E{first_row}:E{total_row - 1})",
        f"=SUM(F{first_row}:F{total_row - 1})",
        f"=SUM(G{first_row}:G{total_row - 1})",
        "",
        "",
        "Formula row for estimated, actual, and variance.",
    ])
    return ["Provider", "Tool", "Owner", "Plan", "Estimated USD", "Actual USD", "Variance USD", "Usage", "Renewal Date", "Savings Notes"], rows


def _budget_rows(topic: str) -> tuple[list[str], list[list[str]]]:
    lowered = topic.lower()
    if any(word in lowered for word in ("household", "home", "monthly", "family")) and not _travel_budget_topic(topic):
        return _household_budget_rows()
    return _travel_budget_rows(lowered)


def _coding_tasks() -> list[tuple[str, str, str, str]]:
    return [
        ("Define skill contract", "High", "Not Started", "Confirm route, input fields, and safety boundary."),
        ("Implement tool call", "High", "Not Started", "Wire the local capability without blocking voice playback."),
        ("Add regression tests", "High", "Not Started", "Cover success, failure, and sensitive-stop behavior."),
        ("Run live smoke", "Medium", "Not Started", "Open the real app or browser and verify visible state."),
        ("Document result", "Medium", "Not Started", "Record what passed, what failed, and next action."),
    ]


def _office_tasks() -> list[tuple[str, str, str, str]]:
    return [
        ("Prepare weekly operations update", "High", "Not Started", "Collect input before Friday."),
        ("Confirm review inputs", "High", "Not Started", "Ask owner to add source numbers."),
        ("Follow up pending approvals", "Medium", "In Progress", "Track blockers and decision owner."),
        ("Review delivery status", "Medium", "Not Started", "Update once delivery date is confirmed."),
        ("Send priority summary", "Low", "Not Started", "Keep summary concise for the team."),
    ]


def _saas_tools() -> list[tuple[str, str, str, str, str]]:
    return [
        ("AI Providers", "Voice or text model", "Owner TBD", "Usage based", "Track monthly usage and alerts."),
        ("Browser Automation", "Research and browser tool", "Owner TBD", "Monthly", "Review whether the tool is still used."),
        ("Document Creation", "Word, Excel, PPTX workflow", "Owner TBD", "Monthly", "Compare output value against subscription cost."),
        ("Design Tools", "Presentation or visual helper", "Owner TBD", "Monthly", "Keep only if it improves delivery quality."),
        ("Cloud Hosting", "Server, storage, logs", "Owner TBD", "Usage based", "Use budgets and alerts per project."),
        ("Productivity", "General SaaS tool", "Owner TBD", "Monthly", "Cancel duplicate or unused seats."),
        ("Security", "Password, monitoring, backup", "Owner TBD", "Annual", "Prioritize renewals that protect core work."),
    ]


def _household_budget_rows() -> tuple[list[str], list[list[str]]]:
    first_row = 4
    rows = []
    for idx, (category, item, frequency, owner, note) in enumerate(_household_categories()):
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


def _household_categories() -> list[tuple[str, str, str, str, str]]:
    return [
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


def _travel_budget_rows(lowered: str) -> tuple[list[str], list[list[str]]]:
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
