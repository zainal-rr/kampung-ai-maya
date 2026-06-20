from __future__ import annotations

import re

from maya_travel.flight_search_models import FieldAttempt, FlightDetails, MONTHS, destination_match_tokens
from maya_travel.travel_booking_safety import travel_booking_safety_footer


def _labels_contain(labels: list[str], value: str) -> bool:
    low = value.lower()
    tokens = [token for token in re.split(r"\W+", low) if len(token) >= 3]
    return any(low in label.lower() or (tokens and all(token in label.lower() for token in tokens[:2])) for label in labels)


def _date_verified(labels: list[str], value: str) -> bool:
    parts = value.split()
    if len(parts) < 2:
        return False
    month = parts[0][:3].lower()
    if not parts[1].isdigit():
        return False
    day = str(int(parts[1]))
    return any(month in label.lower() and day in label for label in labels)


def _current_trip_type(page_text: str) -> str:
    compact = "\n".join(line.strip() for line in page_text.splitlines() if line.strip())
    match = re.search(r"\bFlights?(?:\s+search)?\s*\n\s*(One way|Round trip)\b", compact, re.I)
    if match:
        return match.group(1).lower()
    lines = compact.splitlines()
    for idx, line in enumerate(lines):
        if line in {"Flights", "Flight search"} and idx + 1 < len(lines):
            candidate = lines[idx + 1].strip().lower()
            if candidate in {"one way", "round trip"}:
                return candidate
    return ""


def _ready_for_search(details: FlightDetails, attempts: list[FieldAttempt]) -> bool:
    return not _unverified_required_fields(details, attempts)


def _unverified_required_fields(details: FlightDetails, attempts: list[FieldAttempt]) -> list[str]:
    by_field = {attempt.field: attempt for attempt in attempts}
    required = ["destination", "departure"]
    if details.return_date:
        required.append("return")
    missing = []
    for field in required:
        attempt = by_field.get(field)
        if not attempt or attempt.status not in {"verified", "already set"}:
            missing.append(field)
    return missing


def _workflow_value(details: FlightDetails) -> str:
    return f"flights:origin={details.origin};destination={details.destination};depart={details.depart};return={details.return_date};one_way={details.one_way}"


def _opened_reply(details: FlightDetails) -> str:
    lines = [
        "Flight search skill opened Google Flights with the stable URL only.",
        f"origin: {details.origin}",
        f"destination: {details.destination}",
        f"depart: {details.depart or 'unknown'}",
        f"return: {details.return_date or 'one way'}",
    ]
    if details.assumptions:
        lines.append("assumptions:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(details.assumptions, 1))
    lines.append(travel_booking_safety_footer())
    return "\n".join(lines)


def _clarification_reply(details: FlightDetails) -> str:
    questions = []
    if "departure date" in details.missing:
        questions.append("What departure date should I use?")
    if "destination" in details.missing:
        questions.append("Where are you flying to?")
    if "origin" in details.missing:
        questions.append("Where are you flying from?")
    lines = [
        "Flight search needs one detail before I open Google Flights.",
        f"origin: {details.origin}",
        f"destination: {details.destination or 'unknown'}",
        f"trip type: {'one way' if details.one_way else 'return'}",
        "I will assume one way unless you give me a return date.",
        " ".join(questions[:3]),
    ]
    if details.assumptions:
        lines.append("assumptions:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(details.assumptions, 1))
    if details.missing:
        lines.append("missing: " + ", ".join(details.missing))
    return "\n".join(line for line in lines if line)


def extract_flight_options(text: str, destination: str, depart: str = "", limit: int = 5) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    price_re = re.compile(r"\b(?:MYR|RM)\s*[\d,]+", re.I)
    date_tokens = _date_match_tokens(depart)
    dest_tokens = destination_match_tokens(destination) if destination else ()
    windows = []
    for idx, line in enumerate(lines):
        if not price_re.search(line):
            continue
        windows.append(" | ".join(lines[max(0, idx - 4): min(len(lines), idx + 5)]))

    def dest_ok(joined: str) -> bool:
        return not dest_tokens or any(re.search(rf"\b{re.escape(token)}\b", joined, re.I) for token in dest_tokens)

    def date_ok(joined: str) -> bool:
        return not date_tokens or any(token in joined.lower() for token in date_tokens)

    def flight_row(joined: str) -> bool:
        # Real flight cards show departure times or durations; home-page promo
        # cards ("Penang Jul 9 - Jul 15 from MYR 256") do not.
        return bool(re.search(r"\b\d{1,2}:\d{2}\s*[AP]M\b|\b\d+\s*hr\b|\b\d+\s*min\b", joined, re.I))

    # Every accepted window must look like a real flight card (time/duration),
    # which rejects home-page promo cards. Pass 1 additionally requires the
    # departure date; pass 2 drops it because results pages show the date in
    # the form header, not per option row.
    for predicate in (
        lambda joined: dest_ok(joined) and flight_row(joined) and date_ok(joined),
        lambda joined: dest_ok(joined) and flight_row(joined),
    ):
        options: list[str] = []
        for joined in windows:
            if predicate(joined) and joined not in options:
                options.append(joined)
            if len(options) >= limit:
                break
        if options:
            return options
    if date_tokens or dest_tokens:
        return []
    options = []
    for idx, line in enumerate(lines):
        if not price_re.search(line):
            continue
        joined = " | ".join(lines[max(0, idx - 3): min(len(lines), idx + 4)])
        if joined not in options:
            options.append(joined)
        if len(options) >= limit:
            break
    return options


def extract_date_grid_price(text: str, depart: str) -> str:
    parts = depart.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return ""
    month = parts[0].lower()
    day = str(int(parts[1]))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    month_idx = next((idx for idx, line in enumerate(lines) if line.lower() == month or line.lower().startswith(month[:3])), -1)
    if month_idx == -1:
        return ""
    month_names = {m.lower() for m in MONTHS if len(m) > 3}
    for idx in range(month_idx + 1, min(len(lines), month_idx + 140)):
        line = lines[idx]
        if idx > month_idx + 5 and line.lower() in month_names:
            break
        match = re.fullmatch(rf"{re.escape(day)}\s+(\d{{2,5}})", line)
        if match:
            return f"Date grid for {parts[0].title()} {day}: MYR {match.group(1)} shown by Google Flights; exact airline schedule was not opened yet."
        if line == day and idx + 1 < len(lines) and re.fullmatch(r"\d{2,5}", lines[idx + 1]):
            return f"Date grid for {parts[0].title()} {day}: MYR {lines[idx + 1]} shown by Google Flights; exact airline schedule was not opened yet."
    return ""


def _date_match_tokens(depart: str) -> list[str]:
    parts = depart.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return []
    month = parts[0][:3].lower()
    day = str(int(parts[1]))
    return [f"{month} {day}", f"{parts[0].lower()} {day}"]


def _filled_reply(details: FlightDetails, attempts: list[FieldAttempt], price_options: list[str] | None = None, result_page: str = "") -> str:
    verified = [attempt for attempt in attempts if attempt.status in {"verified", "already set"}]
    failed = [attempt for attempt in attempts if attempt.status not in {"verified", "already set", "skipped"}]
    status = "ready for review" if len(verified) >= 2 and not failed else "needs manual check"
    if details.missing:
        status = "needs clarification"
    lines = [
        "Flight search skill used. Opened Google Flights with the stable URL only.",
        f"status: {status}",
        f"origin: {details.origin}",
        f"destination: {details.destination}",
        f"depart: {details.depart or 'unknown'}",
        f"return: {details.return_date or 'one way'}",
        "field results:",
    ]
    lines.extend(attempt.line() for attempt in attempts)
    if result_page:
        lines.append(f"result page: {result_page}")
    if price_options:
        lines.append("visible price options:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(price_options, 1))
    else:
        lines.append("visible price options: none extracted from page text; use screenshot fallback if prices are visibly shown.")
    if details.assumptions:
        lines.append("assumptions:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(details.assumptions, 1))
    if details.missing:
        lines.append("missing: " + ", ".join(details.missing))
    lines.append(travel_booking_safety_footer(len(price_options or [])))
    return "\n".join(lines)
