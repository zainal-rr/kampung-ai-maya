from __future__ import annotations

import time
from typing import Iterable

from maya_travel.flight_search_models import FieldAttempt, FlightDetails
from maya_travel.flight_search_reply import _current_trip_type, _date_verified, _labels_contain


def field_labels(browser, kinds: set[str] | None = None) -> list[str]:
    allowed = kinds or {"input", "button"}
    return [item.label for item in browser.inspect_elements(120) if item.kind in allowed]


def capture_result_page(skill, page) -> None:
    skill.last_result_page = f"{page.title} | {page.url}"
    skill.last_result_title = page.title
    skill.last_result_url = page.url
    skill.last_result_text = page.text


def close_active_overlay(browser, bridge) -> None:
    try:
        bridge.press_shortcut("escape")
        time.sleep(0.35)
    except Exception:
        pass
    try:
        browser.click_visible_text("Done")
        time.sleep(0.45)
    except Exception:
        pass


def finalize_attempts(skill, details: FlightDetails, attempts: Iterable[FieldAttempt]) -> list[FieldAttempt]:
    input_labels = field_labels(skill.browser, {"input"})
    final: list[FieldAttempt] = []
    for attempt in attempts:
        if attempt.field in {"origin", "destination"}:
            ok = _labels_contain(input_labels, attempt.value)
        elif attempt.field in {"departure", "return"}:
            ok = _date_verified(input_labels, attempt.value)
        else:
            ok = _trip_type_ok(skill.browser, details) if attempt.field == "trip type" else attempt.status in {"verified", "already set"}
        if ok:
            final.append(_verified_attempt(attempt))
        elif attempt.status == "skipped":
            final.append(attempt)
        else:
            final.append(FieldAttempt(attempt.field, attempt.value, "not verified", "not visible in final browser state"))
    return final


def _trip_type_ok(browser, details: FlightDetails) -> bool:
    page = browser.inspect_page(1000).text
    expected = "one way" if details.one_way else "round trip"
    return _current_trip_type(page) == expected


def _verified_attempt(attempt: FieldAttempt) -> FieldAttempt:
    if attempt.status in {"verified", "already set"}:
        return attempt
    return FieldAttempt(attempt.field, attempt.value, "verified", "final state")
