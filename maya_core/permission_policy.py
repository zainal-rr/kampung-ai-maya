from __future__ import annotations

import re
from pathlib import Path


AUTO_ALLOWED_ACTIONS = {
    "follow_up",
    "summarize_history",
    "digest_omi",
    "open_app",
    "create_file",
    "write_file",
    "browse_web",
    "browser_click",
    "travel_search",
    "read_document",
    "create_document",
    "edit_document",
    "create_presentation",
    "edit_presentation",
    "network_check",
    "cloudflare_use",
    "gcp_use",
    "cloud_account_use",
}
CONFIRMATION_ACTIONS = {
    "delete_file",
    "delete_resource",
    "send_message",
    "share_file",
    "upload_file",
    "submit_form",
    "sensitive_browser_click",
    "book_travel",
    "purchase_item",
    "make_payment",
    "run_command",
    "apply_code_patch",
    "deploy_repair",
}
HARD_DENY_ACTIONS = {"expose_private_info"}
SENSITIVE_PATH_PARTS = {
    ".ssh",
    ".gnupg",
    ".aws",
    ".config/gcloud",
    ".docker",
    "Library/LaunchAgents",
    "Library/LaunchDaemons",
    ".zshrc",
    ".zprofile",
    ".bashrc",
    ".bash_profile",
}
SENSITIVE_MARKERS = (
    "seed phrase",
    "recovery phrase",
)
PRIVATE_DATA_PHRASE_CUES = (
    "private notes",
    "saved notes",
    "medical notes",
    "medical records",
    "health records",
    "private medical",
    "bank details",
    "home address",
    "personal address",
    "private address",
    "salary",
    "compensation",
    "saved passwords",
    "personal notes",
)
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xai-[A-Za-z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b\d{6}\b.*\b(?:otp|2fa|code)\b", re.IGNORECASE),
    re.compile(r"\b(?:otp|2fa|code)\b.{0,24}\b\d{6}\b", re.IGNORECASE),
    re.compile(r"\b(?:api[_ -]?key|api[_ -]?token|access[_ -]?token|auth[_ -]?token|bearer[_ -]?token|client[_ -]?secret|secret[_ -]?key)\s*[:=]\s*[A-Za-z0-9_\-]{16,}\b", re.IGNORECASE),
    re.compile(r"\b(?:cvv|cvc)\s*[:=]?\s*\d{3,4}\b", re.IGNORECASE),
    re.compile(r"\b(?:account\s+number|acct\s+no)\s*[:=]?\s*\d{8,20}\b", re.IGNORECASE),
)
CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
EXPOSURE_STARTERS = (
    "show",
    "tell me",
    "send",
    "email",
    "share",
    "reveal",
    "read out",
    "export",
    "upload",
    "publish",
    "copy",
    "paste",
    "print",
    "display",
    "what is",
    "what's",
    "give me",
)


def path_allowed(path: str | Path) -> bool:
    return not path_needs_confirmation(path)


def path_needs_confirmation(path: str | Path) -> bool:
    resolved = Path(path).expanduser().resolve(strict=False)
    text = str(resolved)
    return any(part in text for part in SENSITIVE_PATH_PARTS)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def looks_like_card_number(text: str) -> bool:
    """Luhn-validated card detection: avoids flagging timestamps and phone numbers."""
    for match in CARD_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"[ -]", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return True
    return False


def contains_sensitive_info(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return (
        any(marker in lowered for marker in SENSITIVE_MARKERS)
        or any(pattern.search(text) for pattern in SECRET_PATTERNS)
        or _looks_like_password_secret(text)
        or looks_like_card_number(text)
    )


def _looks_like_password_secret(text: str) -> bool:
    safe_password_terms = {"minimum", "required", "field", "enter", "create", "strong", "choose", "use", "needed"}
    for match in re.finditer(r"\b(?:my\s+|the\s+)?password\s+is\s+([^\s.,;:!?]{4,})", text, re.IGNORECASE):
        token = match.group(1).strip().lower()
        if token not in safe_password_terms:
            return True
    for match in re.finditer(r"\bpassword\s*[:=]\s*([^\s.,;:!?]{4,})", text, re.IGNORECASE):
        token = match.group(1).strip().lower()
        if token not in safe_password_terms:
            return True
    return False


def contains_sensitive_phrase_cue(text: str) -> bool:
    lowered = " ".join(str(text or "").lower().split())
    return any(
        cue in lowered
        for cue in (
            "my password is",
            "my password",
            "the password",
            "password is",
            "my passcode is",
            "api key",
            "api token",
            "access token",
            "bank account",
            "account number",
            *PRIVATE_DATA_PHRASE_CUES,
        )
    )


def is_private_exposure(text: str) -> bool:
    lowered = " ".join(text.lower().strip().split())
    if not (contains_sensitive_info(lowered) or contains_sensitive_phrase_cue(lowered)):
        return False
    if safe_sensitive_guidance(lowered):
        return False
    return lowered.startswith(EXPOSURE_STARTERS)


def safe_sensitive_guidance(text: str) -> bool:
    guidance_markers = (
        "password policy",
        "safe password",
        "password rules",
        "password guidance",
        "what should not be sent",
        "review expense claims safely",
        "handle expense claims safely",
    )
    return any(marker in " ".join(text.lower().split()) for marker in guidance_markers)


def action_permission(action_type: str, content: str = "") -> str:
    if action_type in HARD_DENY_ACTIONS or is_private_exposure(content):
        return "deny"
    if content and contains_sensitive_info(content) and action_type in {
        "create_file",
        "write_file",
        "send_message",
        "share_file",
        "upload_file",
    }:
        return "deny"
    if content and contains_sensitive_phrase_cue(content) and action_type in {
        "send_message",
        "share_file",
        "upload_file",
    }:
        return "confirm"
    if action_type in CONFIRMATION_ACTIONS:
        return "confirm"
    if action_type in AUTO_ALLOWED_ACTIONS:
        return "allow"
    return "confirm"


def hard_no_private_exposure_text() -> str:
    return "I can't expose sensitive private information like passwords, bank details, API keys, tokens, or private keys."


def permission_summary() -> str:
    return (
        "Maya can use local apps, browser research, local folders including Desktop, documents, presentations, "
        "network diagnostics, and configured Cloudflare or GCP accounts. Create, write, browse, and compare are allowed. "
        "Delete, send, upload, form submission, booking, purchases, and payments need confirmation. "
        "Sensitive private exposure is blocked."
    )
