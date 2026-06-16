from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

from maya_voice.tool_results import voice_display_name_from_path, voice_safe_paths


MAX_CONTEXT_CHARS = 9000


@dataclass
class ActiveContext:
    app: str
    selection_type: str
    selected_content: str = ""
    active_file: str = ""
    active_title: str = ""
    nearby_context: str = ""
    document_context: str = ""
    visual_context: str = ""
    limits: str = ""
    source: str = ""
    fallback_used: str = ""
    confidence: float = 0.0
    error: str = ""
    untrusted_influence: bool = False
    injection_detected: bool = False
    untrusted_source: str = ""
    untrusted_signals: tuple[str, ...] = ()
    captured_at: str = ""
    evidence_blocks: str = ""
    verified_facts: str = ""
    instruction_trust: str = ""
    reason_code: str = ""

    def as_tool_text(self) -> str:
        lines = [
            "Active iMac context:",
            f"app: {self.app or 'unknown'}",
            f"selection_type: {self.selection_type or 'unknown'}",
            f"confidence: {self.confidence:.2f}",
            f"context_source: {self.source or 'unknown'}",
        ]
        _append_optional(lines, "active_title", self.active_title)
        active_file_display = voice_display_name_from_path(self.active_file)
        _append_optional(lines, "active_file_display_name", active_file_display)
        if active_file_display:
            lines.append(
                "file_name_guidance: for questions about the saved file's identity, answer from "
                "active_file_display_name. active_title is the content title, not the saved filename."
            )
        _append_optional(lines, "active_path_or_url", self.active_file)
        _append_optional(lines, "fallback_used", self.fallback_used)
        _append_optional(lines, "captured_at", self.captured_at)
        _append_optional(lines, "instruction_trust", self.instruction_trust)
        _append_optional(lines, "reason_code", self.reason_code)
        _append_json_block(lines, "evidence_blocks", self.evidence_blocks, 3600)
        _append_json_block(lines, "verified_facts", self.verified_facts, 1600)
        if self.selected_content:
            lines.append("selected_text_present: true")
            _append_block(lines, "selected_text", self.selected_content, 2600)
        _append_block(lines, "anchor", self.selected_content, 2600)
        _append_block(lines, "nearby_context", self.nearby_context, 2600)
        _append_block(lines, "document_context", self.document_context, 5200)
        _append_block(lines, "visual_context", self.visual_context, 2200)
        _append_block(lines, "limits", self.limits, 1200)
        if self.untrusted_influence:
            lines.append("untrusted_influence: true")
            lines.append(f"injection_detected: {'true' if self.injection_detected else 'false'}")
            _append_optional(lines, "untrusted_source", self.untrusted_source)
            if self.untrusted_signals:
                _append_block(lines, "untrusted_risk_notes", "\n".join(self.untrusted_signals), 1200)
        _append_optional(lines, "error", self.error)
        return voice_safe_paths("\n".join(lines))[:MAX_CONTEXT_CHARS]


def log_context(context: ActiveContext) -> None:
    print(
        "maya-active-context> "
        f"app={context.app or 'unknown'} "
        f"source={context.source or context.fallback_used or 'unknown'} "
        f"type={context.selection_type or 'unknown'} "
        f"path={context.active_file or 'none'} "
        f"title={context.active_title or 'none'} "
        f"doc_chars={len(context.document_context)} "
        f"anchor_chars={len(context.selected_content)} "
        f"untrusted={context.untrusted_influence} "
        f"injection={context.injection_detected}",
        flush=True,
    )


def _append_optional(lines: list[str], key: str, value: str) -> None:
    if value:
        lines.append(f"{key}: {value}")


def _append_block(lines: list[str], key: str, value: str, limit: int) -> None:
    if value:
        lines.append(f"{key}:")
        lines.append(_clip(value, limit))


def _append_json_block(lines: list[str], key: str, value: str, limit: int) -> None:
    if not value:
        return
    try:
        parsed = json.loads(value)
        rendered = json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=True)
    except (TypeError, ValueError):
        rendered = value
    _append_block(lines, key, rendered, limit)


def _clip(text: str, limit: int) -> str:
    clean = html.unescape(str(text)).strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    if len(clean) <= limit:
        return clean
    return clean[: limit - 20].rstrip() + "\n[context clipped]"
