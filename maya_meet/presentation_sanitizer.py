from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
import re

from maya_core.permission_policy import contains_sensitive_info


PRIVATE_PRESENTATION_RE = re.compile(
    r"\b("
    r"private|personal|password|passcode|pin|api\s*key|api\s*token|"
    r"access\s*token|credential|secret|bank|account\s+number|medical"
    r")\b",
    re.IGNORECASE,
)

BLOCKED_TAGS = frozenset({"script", "style", "iframe", "form", "object", "embed", "link", "meta"})
SAFE_TAGS = frozenset({
    "article",
    "aside",
    "blockquote",
    "br",
    "caption",
    "code",
    "dd",
    "div",
    "dl",
    "dt",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "section",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
})
VOID_TAGS = frozenset({"br", "hr"})
HTML_VOID_TAGS = VOID_TAGS | frozenset({"area", "base", "col", "embed", "img", "input", "link", "meta", "source", "track", "wbr"})


@dataclass(frozen=True)
class SanitizedPresentation:
    html: str
    blocked_private: bool = False
    removed_tags: tuple[str, ...] = ()
    removed_attrs: tuple[str, ...] = ()
    reason_code: str = "sanitized"


@dataclass
class _SanitizeState:
    parts: list[str] = field(default_factory=list)
    removed_tags: list[str] = field(default_factory=list)
    removed_attrs: list[str] = field(default_factory=list)
    blocked_depth: int = 0


class _PresentationHTMLSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.state = _SanitizeState()

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = tag.casefold()
        if self.state.blocked_depth:
            if normalized not in HTML_VOID_TAGS:
                self.state.blocked_depth += 1
            return
        if normalized in BLOCKED_TAGS:
            self.state.removed_tags.append(normalized)
            self._record_removed_attrs(normalized, attrs)
            self.state.blocked_depth = 1
            return
        if normalized not in SAFE_TAGS:
            self.state.removed_tags.append(normalized)
            self._record_removed_attrs(normalized, attrs)
            return
        self._record_removed_attrs(normalized, attrs)
        if normalized in VOID_TAGS:
            self.state.parts.append(f"<{normalized}>")
        else:
            self.state.parts.append(f"<{normalized}>")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if self.state.blocked_depth:
            self.state.blocked_depth -= 1
            return
        if normalized in SAFE_TAGS and normalized not in VOID_TAGS:
            self.state.parts.append(f"</{normalized}>")

    def handle_data(self, data: str) -> None:
        if self.state.blocked_depth:
            return
        self.state.parts.append(escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        if not self.state.blocked_depth:
            self.state.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self.state.blocked_depth:
            self.state.parts.append(f"&#{name};")

    def _record_removed_attrs(self, tag: str, attrs) -> None:
        for raw_name, raw_value in attrs or []:
            name = str(raw_name or "").casefold()
            value = str(raw_value or "")
            if name.startswith("on"):
                self.state.removed_attrs.append(f"{tag}.{name}")
                continue
            if name in {"src", "srcset", "href", "action", "formaction"}:
                self.state.removed_attrs.append(f"{tag}.{name}")
                continue
            if _looks_remote_load(value):
                self.state.removed_attrs.append(f"{tag}.{name}")


def sanitize_presentation_html(html: str, *, disclosure_approved: bool = False) -> SanitizedPresentation:
    raw = str(html or "")
    if _contains_private_material(raw) and not disclosure_approved:
        return SanitizedPresentation(
            html="<section><p>Private material withheld pending owner approval.</p></section>",
            blocked_private=True,
            reason_code="private_presentation_requires_approval",
        )
    parser = _PresentationHTMLSanitizer()
    parser.feed(raw)
    parser.close()
    cleaned = "".join(parser.state.parts)
    return SanitizedPresentation(
        html=cleaned,
        blocked_private=False,
        removed_tags=tuple(parser.state.removed_tags),
        removed_attrs=tuple(parser.state.removed_attrs),
        reason_code="sanitized",
    )


def _looks_remote_load(value: str) -> bool:
    lowered = str(value or "").strip().casefold()
    return lowered.startswith(("http://", "https://", "//", "data:", "javascript:"))


def _contains_private_material(text: str) -> bool:
    value = str(text or "")
    return bool(PRIVATE_PRESENTATION_RE.search(value) or contains_sensitive_info(value))
