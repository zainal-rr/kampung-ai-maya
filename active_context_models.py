from __future__ import annotations

import html
import re
from dataclasses import dataclass


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

    def as_tool_text(self) -> str:
        lines = [
            "Active iMac context:",
            f"app: {self.app or 'unknown'}",
            f"selection_type: {self.selection_type or 'unknown'}",
            f"confidence: {self.confidence:.2f}",
            f"context_source: {self.source or 'unknown'}",
        ]
        _append_optional(lines, "active_title", self.active_title)
        _append_optional(lines, "active_path_or_url", self.active_file)
        _append_optional(lines, "fallback_used", self.fallback_used)
        _append_block(lines, "anchor", self.selected_content, 2600)
        _append_block(lines, "nearby_context", self.nearby_context, 2600)
        _append_block(lines, "document_context", self.document_context, 5200)
        _append_block(lines, "visual_context", self.visual_context, 2200)
        _append_block(lines, "limits", self.limits, 1200)
        _append_optional(lines, "error", self.error)
        return "\n".join(lines)[:MAX_CONTEXT_CHARS]


def log_context(context: ActiveContext) -> None:
    print(
        "maya-active-context> "
        f"app={context.app or 'unknown'} "
        f"source={context.source or context.fallback_used or 'unknown'} "
        f"type={context.selection_type or 'unknown'} "
        f"path={context.active_file or 'none'} "
        f"title={context.active_title or 'none'} "
        f"doc_chars={len(context.document_context)} "
        f"anchor_chars={len(context.selected_content)}",
        flush=True,
    )


def _append_optional(lines: list[str], key: str, value: str) -> None:
    if value:
        lines.append(f"{key}: {value}")


def _append_block(lines: list[str], key: str, value: str, limit: int) -> None:
    if value:
        lines.append(f"{key}:")
        lines.append(_clip(value, limit))


def _clip(text: str, limit: int) -> str:
    clean = html.unescape(str(text)).strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    if len(clean) <= limit:
        return clean
    return clean[: limit - 20].rstrip() + "\n[context clipped]"
