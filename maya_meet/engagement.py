from __future__ import annotations

import re


GREETING_ADDRESS_RE = re.compile(r"^\s*(?:hey|hi|okay|ok|yo)\s+maya\b[,\s:;-]*(.*)$", re.IGNORECASE)
PUNCTUATED_ADDRESS_RE = re.compile(r"^\s*maya\s*[,;:-]\s*(.*)$", re.IGNORECASE)
BARE_ADDRESS_RE = re.compile(r"^\s*maya\s+(.+)$", re.IGNORECASE)
REFERENCE_START_RE = re.compile(r"^(?:is|was|were|has|had|will|looks|sounds|seems|appears)\b", re.IGNORECASE)


def _address_remainder(text: str) -> str | None:
    raw = str(text or "")
    for pattern in (GREETING_ADDRESS_RE, PUNCTUATED_ADDRESS_RE):
        match = pattern.match(raw)
        if match and match.group(1).strip():
            return match.group(1).strip()
    match = BARE_ADDRESS_RE.match(raw)
    if not match:
        return None
    remainder = match.group(1).strip()
    if not remainder or REFERENCE_START_RE.match(remainder):
        return None
    return remainder


def addressed_to_maya(text: str) -> bool:
    return _address_remainder(text) is not None


def strip_maya_address(text: str) -> str:
    return _address_remainder(text) or str(text or "").strip()
