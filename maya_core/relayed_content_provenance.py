from __future__ import annotations

import re

from maya_core.provenance import ProvenanceContext, make_provenance, provenance_from_source_channel
from maya_core.untrusted_input_boundary import assess_untrusted_content


_EMAIL_MARKERS = (
    "email body",
    "owner email contains",
    "quoted email",
    "relayed email",
    "email says",
    "inbox says",
)
_WEB_MARKERS = (
    "relayed webpage",
    "quoted webpage",
    "webpage says",
    "website says",
    "page says",
    "browser page says",
)
_DOCUMENT_MARKERS = (
    "document says",
    "file says",
    "pdf says",
    "quoted document",
    "relayed document",
)
_MEETING_MARKERS = (
    "meeting transcript",
    "meet transcript",
    "room audio says",
    "another speaker says",
)


def provenance_for_channel_text(channel: str, text: str, *, source_ref: str = "") -> ProvenanceContext:
    """Return provenance for text received on a channel.

    The transport can be trusted while the quoted payload is not. For example,
    an owner may paste a webpage or email into Telegram. That proves the owner
    sent the message, but it does not promote the webpage/email values to
    owner-trusted control facts. This helper preserves that distinction.
    """
    base = provenance_from_source_channel(channel, source_ref=source_ref)
    relayed_source = relayed_untrusted_source_kind(text)
    if not relayed_source:
        return base
    assessment = assess_untrusted_content(text, source=_boundary_source(relayed_source))
    return make_provenance(
        relayed_source,
        source_id=source_ref,
        untrusted_influence=True,
        injection_detected=assessment.injection_detected,
        risk_notes=("owner_relayed_untrusted_content", *assessment.signals),
    )


def relayed_untrusted_source_kind(text: str) -> str:
    lowered = " ".join(str(text or "").lower().split())
    if not lowered:
        return ""
    if _has_marker(lowered, _EMAIL_MARKERS):
        return "email"
    if _has_marker(lowered, _WEB_MARKERS):
        return "browser_page"
    if _has_marker(lowered, _DOCUMENT_MARKERS):
        return "office_document"
    if _has_marker(lowered, _MEETING_MARKERS):
        return "meeting_transcript"
    return ""


def _has_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(marker)}\b", text) for marker in markers)


def _boundary_source(source_kind: str) -> str:
    if source_kind == "browser_page":
        return "browser"
    if source_kind == "office_document":
        return "document"
    if source_kind == "meeting_transcript":
        return "meeting_transcript"
    return source_kind
