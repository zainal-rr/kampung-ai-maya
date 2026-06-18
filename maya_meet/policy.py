from __future__ import annotations

from maya_core.provenance import ensure_provenance
from maya_meet.engagement import addressed_to_maya
from maya_meet.models import IRREVERSIBLE_ACTIONS, REVERSIBLE_ACTIONS, MeetingDecision


PRIVATE_CONTENT_CLASSES = frozenset({"owner_private", "protected_personal", "secret", "private_memory", "private_file"})
CONTAINED_ROOM_ACTIONS = frozenset({"lookup", "draft", "scratch_artifact", "summarize", "open_view"})
APPROVAL_ONLY_ACTIONS = IRREVERSIBLE_ACTIONS | frozenset({
    "approval_required",
    "approval_attempt",
    "unknown_action",
    "private_lookup",
})


def meeting_turn_decision(
    *,
    text: str,
    provenance,
    action_class: str = "answer",
    content_class: str = "meeting_public",
    m2_enabled: bool = False,
    voiceprint_verified: bool = False,
) -> MeetingDecision:
    if not addressed_to_maya(text):
        return MeetingDecision("ignored", "not_addressed")
    prov = ensure_provenance(provenance, default_kind="other_speaker")
    action = str(action_class or "answer").strip().lower()
    content = str(content_class or "meeting_public").strip().lower()
    if content in PRIVATE_CONTENT_CLASSES or content in {"unknown", "uncertain"}:
        return MeetingDecision("needs_confirmation", "owner_private_disclosure_requires_telegram", prov.source_kind)
    if action == "answer":
        return MeetingDecision("answer_allowed", "addressed_public_context", prov.source_kind)
    if action == "approval_attempt":
        return MeetingDecision("blocked", "meeting_room_audio_cannot_approve", prov.source_kind)
    if not m2_enabled:
        return MeetingDecision("blocked", "meeting_room_actions_disabled", prov.source_kind)
    if action in CONTAINED_ROOM_ACTIONS and action in REVERSIBLE_ACTIONS:
        return MeetingDecision("allowed", "meeting_room_contained_reversible_action", prov.source_kind)
    if action in APPROVAL_ONLY_ACTIONS or action not in CONTAINED_ROOM_ACTIONS:
        return MeetingDecision("needs_confirmation", "meeting_action_requires_owner_telegram_approval", prov.source_kind)
    return MeetingDecision("needs_confirmation", "meeting_action_requires_owner_telegram_approval", prov.source_kind)
