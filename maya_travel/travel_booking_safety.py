from __future__ import annotations

import re

from maya_core.permission_policy import contains_sensitive_info, hard_no_private_exposure_text


FINAL_ACTION_RE = re.compile(r"\b(book|reserve|purchase|pay|checkout|submit|confirm booking|complete booking)\b", re.I)
EXACT_SELECTION_RE = re.compile(r"\b(option|listing|flight|hotel|stay|room|result)\s*(?:number\s*)?(\d+)\b", re.I)
TRAVEL_PRIVATE_RE = re.compile(
    r"\b(passport|ic|identity card|id card|national id|card|credit card|debit card|cvv|otp|2fa|password|bank|private identifier)\b",
    re.I,
)


def travel_booking_safety_footer(option_count: int = 0) -> str:
    review = "compare the visible options" if option_count != 1 else "review this visible option"
    choose = "tell me the exact option number or name to inspect next"
    confirm = "I will ask for explicit final confirmation before any booking, reserve, purchase, checkout, upload, or submit action."
    sensitive = "I will not handle card, bank, passport, password, OTP, token, API-key, or private identifier details."
    return f"next: {review}; then {choose}. {confirm} {sensitive}"


def travel_booking_boundary_reply(text: str) -> str | None:
    if contains_sensitive_info(text) or TRAVEL_PRIVATE_RE.search(text):
        return hard_no_private_exposure_text()
    lowered = " ".join(text.lower().split())
    if FINAL_ACTION_RE.search(lowered):
        if EXACT_SELECTION_RE.search(lowered):
            return (
                "I can inspect or prepare that exact travel option, but I have not booked anything. "
                + travel_booking_safety_footer(1)
            )
        return (
            "I can help research or compare travel options first, and I stop before booking. "
            "After that, tell me the exact option number or name. "
            + travel_booking_safety_footer()
        )
    return None
