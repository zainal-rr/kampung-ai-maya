from __future__ import annotations

from dataclasses import dataclass


ROOM_LEVEL_LOCKED = "level_0_locked"
VOICEPRINT_STATUSES = {"not_enrolled", "pending_samples", "enrolled", "revoked"}
REVERSIBLE_ACTIONS = frozenset({"answer", "lookup", "open_view", "draft", "summarize", "agenda_mark", "scratch_artifact"})
IRREVERSIBLE_ACTIONS = frozenset({
    "send",
    "delete",
    "overwrite",
    "submit",
    "login",
    "payment",
    "booking",
    "upload",
    "export",
    "repo_write",
    "command",
    "external",
})


@dataclass(frozen=True)
class MeetingDecision:
    status: str
    reason_code: str
    source_kind: str = "other_speaker"
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "source_kind": self.source_kind,
            "detail": self.detail,
        }
