from __future__ import annotations

import re

from permission_policy import hard_no_private_exposure_text, is_private_exposure
from travel_booking_safety import travel_booking_boundary_reply


def safety_action_reply(text: str) -> str | None:
    cleaned = " ".join(text.lower().strip().split())
    if is_private_exposure(cleaned):
        return hard_no_private_exposure_text()
    if _looks_like_delete_file(cleaned):
        return (
            "Deleting files needs confirmation. I have not deleted anything. "
            "Tell me the exact file path if you really want me to queue a delete request."
        )
    if _looks_like_sensitive_browser_action(cleaned):
        return travel_booking_boundary_reply(text) or (
            "I can help research or compare, but I stop before booking, payment, upload, "
            "login submission, or final submit actions unless you explicitly confirm the exact action."
        )
    return None


def _looks_like_delete_file(text: str) -> bool:
    if re.match(r"^(?:delete|remove)\s+(?:my\s+)?tasks?\b", text):
        return False
    if not re.match(r"^(?:delete|remove|erase|trash)\b", text):
        return False
    file_markers = (
        "file", "md", "markdown", "docx", "word", "pptx", "powerpoint",
        "xlsx", "excel", "pdf", ".md", ".docx", ".pptx", ".xlsx",
    )
    return any(marker in text for marker in file_markers)


def _looks_like_sensitive_browser_action(text: str) -> bool:
    if re.match(r"^(?:approve|test|activate|disable|edit|show)\s+skill\b", text):
        return False
    if _looks_like_local_document_send(text):
        return False
    starters = (
        "book", "buy", "purchase", "pay", "checkout", "submit", "upload",
        "send", "login", "log in",
    )
    sensitive_fields = ("passport", "card", "otp", "2fa")
    return (
        any(re.match(rf"^{re.escape(marker)}\b", text) for marker in starters)
        or any(re.search(rf"\b{re.escape(marker)}\b", text) for marker in sensitive_fields)
    )


def _looks_like_local_document_send(text: str) -> bool:
    return bool(
        re.match(
            r"^send(?:\s+me)?\s+(?:the\s+)?(?:last|latest)\s+(?:document|doc|file|artifact)$",
            text,
        )
    )
