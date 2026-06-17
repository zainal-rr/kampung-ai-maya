from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping


OWNER_SOURCES = frozenset({"owner_voice", "owner_text"})
TRUSTED_INTERNAL_SOURCES = frozenset({"maya_internal"})
UNTRUSTED_SOURCE_KINDS = frozenset({
    "browser_page",
    "screen_ocr",
    "office_document",
    "meeting_transcript",
    "other_speaker",
    "unknown",
})
SOURCE_KINDS = OWNER_SOURCES | TRUSTED_INTERNAL_SOURCES | UNTRUSTED_SOURCE_KINDS | frozenset({"memory_recall"})

SOURCE_CHANNEL_MAP = {
    "imac": "owner_voice",
    "imac_voice": "owner_voice",
    "voice": "owner_voice",
    "telegram": "owner_text",
    "browser": "browser_page",
    "web": "browser_page",
    "page": "browser_page",
    "screen": "screen_ocr",
    "document": "office_document",
    "office": "office_document",
    "omi": "meeting_transcript",
    "meeting": "meeting_transcript",
    "meeting_speech": "other_speaker",
    "recall_speech": "other_speaker",
    "other_speaker": "other_speaker",
}


@dataclass(frozen=True)
class ProvenanceContext:
    source_kind: str = "unknown"
    source_id: str = ""
    untrusted_influence: bool = True
    injection_detected: bool = False
    risk_notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "untrusted_influence": self.untrusted_influence,
            "injection_detected": self.injection_detected,
            "risk_notes": list(self.risk_notes),
        }


def normalize_source_kind(value: str | None) -> str:
    kind = str(value or "").strip().lower()
    return kind if kind in SOURCE_KINDS else "unknown"


def default_untrusted_for_source(source_kind: str) -> bool:
    kind = normalize_source_kind(source_kind)
    if kind in OWNER_SOURCES or kind in TRUSTED_INTERNAL_SOURCES:
        return False
    return True


def make_provenance(
    source_kind: str | None = "unknown",
    *,
    source_id: str = "",
    untrusted_influence: bool | None = None,
    injection_detected: bool = False,
    risk_notes: tuple[str, ...] | list[str] = (),
) -> ProvenanceContext:
    kind = normalize_source_kind(source_kind)
    untrusted = default_untrusted_for_source(kind) if untrusted_influence is None else bool(untrusted_influence)
    return ProvenanceContext(
        source_kind=kind,
        source_id=str(source_id or ""),
        untrusted_influence=untrusted,
        injection_detected=bool(injection_detected),
        risk_notes=tuple(str(item) for item in risk_notes if str(item).strip()),
    )


def trusted_owner_voice() -> ProvenanceContext:
    return make_provenance("owner_voice")


def trusted_owner_text() -> ProvenanceContext:
    return make_provenance("owner_text")


def provenance_from_source_channel(source_channel: str, *, source_ref: str = "") -> ProvenanceContext:
    kind = SOURCE_CHANNEL_MAP.get(str(source_channel or "").strip().lower(), "unknown")
    return make_provenance(kind, source_id=source_ref)


def provenance_from_json(value: str | Mapping[str, Any] | None, *, default_kind: str = "unknown") -> ProvenanceContext:
    if isinstance(value, Mapping):
        data = dict(value)
    else:
        try:
            data = json.loads(str(value or "").strip() or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            data = {}
    return make_provenance(
        data.get("source_kind") or data.get("source") or default_kind,
        source_id=str(data.get("source_id") or ""),
        untrusted_influence=data.get("untrusted_influence") if "untrusted_influence" in data else None,
        injection_detected=bool(data.get("injection_detected")),
        risk_notes=tuple(data.get("risk_notes") or data.get("signals") or ()),
    )


def provenance_to_json(provenance: ProvenanceContext | Mapping[str, Any] | None) -> str:
    prov = ensure_provenance(provenance)
    return json.dumps(prov.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def ensure_provenance(value: ProvenanceContext | Mapping[str, Any] | None, *, default_kind: str = "unknown") -> ProvenanceContext:
    if isinstance(value, ProvenanceContext):
        return value
    return provenance_from_json(value, default_kind=default_kind)


def provenance_from_tool_args(args: Mapping[str, Any] | None, *, default_kind: str = "owner_voice") -> ProvenanceContext:
    data = dict(args or {})
    if isinstance(data.get("provenance"), Mapping):
        return provenance_from_json(data["provenance"], default_kind=default_kind)
    if data.get("source_kind") or data.get("source"):
        return make_provenance(
            str(data.get("source_kind") or data.get("source")),
            source_id=str(data.get("source_id") or ""),
            untrusted_influence=data.get("untrusted_influence") if "untrusted_influence" in data else None,
            injection_detected=bool(data.get("injection_detected")),
            risk_notes=tuple(data.get("risk_notes") or data.get("signals") or ()),
        )
    return make_provenance(default_kind)


def memory_recall_provenance(memory_id: str, stored: ProvenanceContext | Mapping[str, Any] | None) -> ProvenanceContext:
    base = ensure_provenance(stored, default_kind="unknown")
    return make_provenance(
        "memory_recall",
        source_id=memory_id,
        untrusted_influence=base.untrusted_influence,
        injection_detected=base.injection_detected,
        risk_notes=base.risk_notes,
    )


def merge_provenance(*items: ProvenanceContext | Mapping[str, Any] | None) -> ProvenanceContext:
    provenances = [ensure_provenance(item) for item in items if item is not None]
    if not provenances:
        return make_provenance("unknown")
    untrusted = any(item.untrusted_influence for item in provenances)
    injection = any(item.injection_detected for item in provenances)
    source = next((item.source_kind for item in provenances if item.untrusted_influence), provenances[0].source_kind)
    source_id = next((item.source_id for item in provenances if item.source_id), "")
    notes: list[str] = []
    for item in provenances:
        notes.extend(item.risk_notes)
    return make_provenance(
        source,
        source_id=source_id,
        untrusted_influence=untrusted,
        injection_detected=injection,
        risk_notes=tuple(dict.fromkeys(notes)),
    )


def can_authorize_confirmation(provenance: ProvenanceContext | Mapping[str, Any] | None) -> bool:
    return ensure_provenance(provenance, default_kind="unknown").source_kind in OWNER_SOURCES


def provenance_lines(provenance: ProvenanceContext | Mapping[str, Any] | None) -> str:
    prov = ensure_provenance(provenance)
    lines = [
        "provenance:",
        f"  source_kind: {prov.source_kind}",
        f"  source_id: {prov.source_id}",
        f"  untrusted_influence: {'true' if prov.untrusted_influence else 'false'}",
        f"  injection_detected: {'true' if prov.injection_detected else 'false'}",
    ]
    if prov.risk_notes:
        lines.append("  risk_notes: " + ", ".join(prov.risk_notes))
    return "\n".join(lines)


def provenance_action_decision(
    *,
    tool_name: str,
    provenance: ProvenanceContext | Mapping[str, Any] | None,
    side_effect_level: str,
) -> tuple[str, str]:
    prov = ensure_provenance(provenance)
    level = str(side_effect_level or "unknown").strip().lower()
    if not prov.untrusted_influence and not prov.injection_detected:
        return "allow", "trusted provenance"
    if level == "read":
        return "allow", "untrusted reference read only"
    if prov.injection_detected and level in {"external", "repo_write", "command", "delete", "unknown"}:
        return "deny", f"{tool_name} blocked because injected untrusted content influenced a high-risk action"
    if level in {"write", "external", "repo_write", "command", "delete", "unknown"}:
        return "confirm", f"{tool_name} requires owner confirmation because the action is untrusted-derived"
    return "confirm", f"{tool_name} requires owner confirmation because provenance is untrusted"
