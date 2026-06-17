from __future__ import annotations

from maya_core.provenance import ensure_provenance
from maya_meet.engagement import addressed_to_maya
from maya_meet.models import IRREVERSIBLE_ACTIONS, REVERSIBLE_ACTIONS, MeetingDecision


PRIVATE_CONTENT_CLASSES = frozenset({"owner_private", "protected_personal", "secret", "private_memory", "private_file"})


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
    if content in PRIVATE_CONTENT_CLASSES:
        return MeetingDecision("owner_channel_only", "owner_private_disclosure_blocked", prov.source_kind)
    if prov.source_kind != "owner_voice_meeting":
        if action == "answer":
            return MeetingDecision("answer_allowed", "addressed_public_context", prov.source_kind)
        return MeetingDecision("blocked", "meeting_other_speaker_cannot_act", prov.source_kind)
    if not m2_enabled:
        return MeetingDecision("blocked", "meeting_m2_disabled", prov.source_kind)
    if not voiceprint_verified:
        return MeetingDecision("blocked", "voiceprint_fresh_verification_required", prov.source_kind)
    if action in REVERSIBLE_ACTIONS:
        return MeetingDecision("allowed", "verified_owner_reversible_action", prov.source_kind)
    if action in IRREVERSIBLE_ACTIONS:
        return MeetingDecision("blocked", "irreversible_action_out_of_meeting_scope", prov.source_kind)
    return MeetingDecision("blocked", "unsupported_meeting_action_class", prov.source_kind)
