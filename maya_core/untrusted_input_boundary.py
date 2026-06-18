"""Untrusted-input boundary: prompt-injection containment (council review W7).

The permission kernel already gates ACTIONS by type regardless of who asked.
The gap this module closes is EXFILTRATION-via-injection: content Maya reads
from a surface she does not control (a web page, an Omi transcript, a screen,
a document) that tries to make her read sensitive data and send it through an
otherwise-allowed channel — or that tries to widen her permission scope.

Design (council directive): "page/transcript content can inform answers but
can never widen scope or trigger external sends unprompted." This is a POLICY
LAYER on top of the existing kernel, not a rebuild.

Two ideas:

1. Content from read-surfaces is UNTRUSTED. `assess_untrusted_content(text)`
   scores injection signals in it (imperative overrides, scope-widening,
   exfiltration asks).
2. When an action with external reach (send/upload/share/submit/payment) or a
   scope-widening action is about to run AND untrusted content with injection
   signals influenced this turn, `untrusted_action_decision(...)` forces a
   human gate ("confirm") or a hard "deny" — it can never silently "allow".

The module is pure logic and deterministic so it is unit-testable without any
live model. Integration points (for the owning session) are documented at the
bottom and exercised by `untrusted_input_boundary_smoke.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Surfaces whose content Maya does not author and must treat as untrusted.
UNTRUSTED_SOURCES = frozenset({
    "browser", "screen", "omi", "document", "web", "page", "email", "pdf",
    "browser_page", "screen_ocr", "office_document", "memory_recall",
    "meeting_transcript", "other_speaker", "unknown",
})

# External-reach actions: anything that moves data OUT of Maya's local boundary.
# Natural-language action_type names (used by the harness action layer).
EXTERNAL_REACH_ACTIONS = frozenset({
    "send_message", "share_file", "upload_file", "submit_form", "make_payment",
    "purchase_item", "book_travel", "telegram_send", "post_content", "email_send",
    # registry tool names (dotted) — the real external tools:
    "telegram.send_file", "mcp.call",
})

# Actions that change what Maya is allowed to do.
SCOPE_WIDENING_ACTIONS = frozenset({
    "grant_permission", "disable_safety", "change_policy", "add_allowlist",
    "elevate", "run_command", "apply_code_patch", "deploy_repair",
    "repo.apply_patch",
})

# AUTHORITATIVE source of "is this external/scope-widening": the tool
# registry's MayaToolSpec.side_effect_level. The action-name sets above are a
# fallback for callers that only have a natural-language action_type.
# (Code-review W7-bug, 2026-06-11: the hardcoded sets alone missed the dotted
# registry tool names, so the boundary failed OPEN on the genuinely external
# tools. Registry-driven resolution + fail-closed-on-unknown is the fix.)
EXTERNAL_SIDE_EFFECTS = frozenset({"external"})
WIDENING_SIDE_EFFECTS = frozenset({"repo_write"})
LOCAL_SIDE_EFFECTS = frozenset({"read", "write"})

# Clearly-local natural-language action names (no external reach). Mirrors the
# safe/local half of permission_policy.AUTO_ALLOWED_ACTIONS. Lets callers that
# pass only an action_type (no side_effect_level) avoid false gates, while
# genuinely UNKNOWN actions still fail closed.
LOCAL_ACTIONS = frozenset({
    "follow_up", "summarize_history", "digest_omi", "open_app",
    "create_file", "write_file", "read_document", "create_document",
    "edit_document", "create_presentation", "edit_presentation",
    "browse_web", "browser_click", "travel_search", "network_check",
})


def _resolve_reach(action_type: str, side_effect_level: str | None) -> tuple[bool, bool, bool]:
    """Return (external, widening, fail_closed_unknown).

    fail_closed_unknown is True when we cannot positively classify the action
    as local — an unknown tool with no side-effect info is treated as
    external-equivalent, so it gets gated under untrusted influence rather
    than slipping through (the same fail-open class W1 just fixed)."""
    action = str(action_type).strip()
    lvl = (side_effect_level or "").strip().lower()
    external = lvl in EXTERNAL_SIDE_EFFECTS or action in EXTERNAL_REACH_ACTIONS
    widening = lvl in WIDENING_SIDE_EFFECTS or action in SCOPE_WIDENING_ACTIONS
    classified_local = (
        lvl in LOCAL_SIDE_EFFECTS
        or action in LOCAL_ACTIONS
        or external
        or widening
    )
    fail_closed_unknown = not classified_local
    return external, widening, fail_closed_unknown

# Imperative-override injection patterns ("ignore your instructions", ...).
_OVERRIDE_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:your\s+|the\s+|previous\s+|prior\s+|above\s+)?(?:instructions?|rules?|prompts?|guidelines?)\b", re.I),
    re.compile(r"\bdisregard\s+(?:your\s+|the\s+|previous\s+|all\s+)", re.I),
    re.compile(r"\bforget\s+(?:your\s+|all\s+|the\s+|previous\s+)?(?:instructions?|rules?|guidelines?|training)\b", re.I),
    re.compile(r"\byou\s+are\s+now\b|\bnew\s+(?:instructions?|rules?|persona|role)\s*[:.]", re.I),
    re.compile(r"\bsystem\s+prompt\b|\boverride\s+(?:your\s+|the\s+)?(?:safety|rules|policy)", re.I),
    re.compile(r"\b(?:act|behave|respond)\s+as\s+(?:if|though)\b.*\b(?:no|without)\s+(?:restrictions?|rules?|limits?)", re.I),
)

_TASK_DEFERRAL_PATTERNS = (
    re.compile(
        r"\b(?:before|prior\s+to)\b.{0,140}\b"
        r"(?:task|request|answer|respond|reply|solve|complete|finish)\b",
        re.I | re.S,
    ),
    re.compile(
        r"\b(?:after|once|when)\b.{0,80}\b(?:done|finished|complete|completed)\b.{0,140}\b"
        r"(?:task|request|answer|respond|reply|solve|continue|resume|return)\b",
        re.I | re.S,
    ),
)

_DIRECTIVE_CUE_PATTERNS = (
    re.compile(r"\b(?:do|perform|execute|complete|carry\s+out)\b.{0,80}\b(?:first|instead|before|instruction|task|request|following)\b", re.I | re.S),
    re.compile(r"\b(?:strictly\s+adhere|follow|obey)\b.{0,80}\b(?:instruction|request|task|order)\b", re.I | re.S),
    re.compile(r"^\s*(?:todo|action\s*item)\s*:\s*\S+", re.I | re.M),
    re.compile(r"\b(?:tell|say|respond|reply)\b.{0,40}\b(?:the\s+user|that|with)\b", re.I | re.S),
)

_TODO_DIRECTIVE_PATTERN = re.compile(
    r"^\s*todo\s*:\s*(?:ignore|send|email|share|post|upload|open|visit|invite|remove|add|book|reserve|delete|update|say|tell|respond)\b",
    re.I | re.M,
)

_ASSISTANT_TARGET_PATTERNS = (
    re.compile(r"\b(?:assistant|model|ai\s+language\s+model|gpt|chatgpt|maya)\b", re.I),
    re.compile(r"\b(?:your|the)\s+(?:task|instructions?|rules?|system\s+prompt)\b", re.I),
)

# Exfiltration asks: read something sensitive and move it out.
_EXFIL_PATTERNS = (
    re.compile(r"\b(?:send|email|forward|upload|post|share|exfiltrate|leak|transmit)\b.{0,40}\b(?:to|@|http|www\.|address|server|webhook)\b", re.I),
    re.compile(r"\b(?:read|open|fetch|copy|export)\b.{0,40}\b(?:\.ssh|\.env|password|secret|api[_\s-]?key|token|credential|private\s+key|wallet|seed\s+phrase)\b", re.I),
    re.compile(r"\b(?:send|share|post)\b.{0,30}\b(?:my|the|his|her|their|user'?s?)\b.{0,20}\b(?:password|token|secret|key|bank|card|account|data|memory|memories)\b", re.I),
)

# Scope-widening asks expressed in natural language inside untrusted content.
_SCOPE_PATTERNS = (
    re.compile(r"\b(?:grant|give|enable|allow)\b.{0,30}\b(?:yourself|full|admin|root|all)\b.{0,20}\b(?:access|permission|privileges?|rights?)\b", re.I),
    re.compile(r"\b(?:disable|turn\s+off|bypass|skip)\b.{0,20}\b(?:safety|approval|confirmation|guard|filter|permission)", re.I),
    re.compile(r"\badd\b.{0,20}\bto\b.{0,20}\ballow\s*list\b|\bwhitelist\b", re.I),
)


@dataclass(frozen=True)
class UntrustedAssessment:
    source: str
    is_untrusted: bool
    injection_detected: bool
    signals: tuple[str, ...] = field(default_factory=tuple)

    @property
    def risk(self) -> str:
        if not self.is_untrusted:
            return "trusted"
        return "injection" if self.injection_detected else "untrusted_clean"


@dataclass(frozen=True)
class UntrustedInputContext:
    source: str
    source_id: str = ""
    untrusted_influence: bool = False
    injection_detected: bool = False
    risk_notes: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def trusted(cls, source: str = "user", source_id: str = "") -> "UntrustedInputContext":
        return cls(source=source, source_id=source_id)

    @classmethod
    def from_assessment(
        cls,
        assessment: UntrustedAssessment,
        *,
        source_id: str = "",
    ) -> "UntrustedInputContext":
        return cls(
            source=assessment.source,
            source_id=source_id,
            untrusted_influence=assessment.is_untrusted,
            injection_detected=assessment.injection_detected,
            risk_notes=assessment.signals,
        )

    @property
    def risk(self) -> str:
        if not self.untrusted_influence:
            return "trusted"
        return "injection" if self.injection_detected else "untrusted_clean"

    def merge(self, other: "UntrustedInputContext") -> "UntrustedInputContext":
        source = self.source if self.source == other.source else "+".join(
            item for item in (self.source, other.source) if item
        )
        source_id = self.source_id or other.source_id
        notes = tuple(dict.fromkeys((*self.risk_notes, *other.risk_notes)))
        return UntrustedInputContext(
            source=source or other.source,
            source_id=source_id,
            untrusted_influence=self.untrusted_influence or other.untrusted_influence,
            injection_detected=self.injection_detected or other.injection_detected,
            risk_notes=notes,
        )


@dataclass(frozen=True)
class BoundaryDecision:
    decision: str          # "allow" | "confirm" | "deny"
    reason: str
    action_type: str
    forced_gate: bool = False


def is_untrusted_source(source: str) -> bool:
    return str(source).strip().lower() in UNTRUSTED_SOURCES


def assess_untrusted_content(text: str, *, source: str = "browser") -> UntrustedAssessment:
    """Score injection signals in content read from an untrusted surface."""
    untrusted = is_untrusted_source(source)
    if not untrusted or not str(text).strip():
        return UntrustedAssessment(source=source, is_untrusted=untrusted, injection_detected=False)
    signals: list[str] = []
    if any(p.search(text) for p in _OVERRIDE_PATTERNS):
        signals.append("instruction_override")
    if any(p.search(text) for p in _EXFIL_PATTERNS):
        signals.append("exfiltration_request")
    if any(p.search(text) for p in _SCOPE_PATTERNS):
        signals.append("scope_widening_request")
    if _looks_like_embedded_task_directive(text):
        signals.append("embedded_task_directive")
    return UntrustedAssessment(
        source=source,
        is_untrusted=True,
        injection_detected=bool(signals),
        signals=tuple(signals),
    )


def _looks_like_embedded_task_directive(text: str) -> bool:
    """Detect task-steering instructions by shape, not by a known attack string."""
    value = str(text or "")
    if not value.strip():
        return False
    has_deferral = any(pattern.search(value) for pattern in _TASK_DEFERRAL_PATTERNS)
    has_directive = any(pattern.search(value) for pattern in _DIRECTIVE_CUE_PATTERNS)
    has_assistant_target = any(pattern.search(value) for pattern in _ASSISTANT_TARGET_PATTERNS)
    if has_deferral and has_directive:
        return True
    if has_directive and has_assistant_target:
        return True
    if _TODO_DIRECTIVE_PATTERN.search(value):
        return True
    return False


def assess_untrusted_context(
    text: str,
    *,
    source: str = "browser",
    source_id: str = "",
) -> UntrustedInputContext:
    return UntrustedInputContext.from_assessment(
        assess_untrusted_content(text, source=source),
        source_id=source_id,
    )


def untrusted_action_decision(
    action_type: str,
    *,
    untrusted_influence: bool,
    injection_detected: bool,
    base_decision: str = "allow",
    side_effect_level: str | None = None,
) -> BoundaryDecision:
    """Final boundary check, applied AFTER the normal permission kernel.

    "External reach" is resolved from the tool registry's side_effect_level
    when available, with the action-name sets as fallback, and unknown actions
    treated as external (fail-closed). Rules (never relax the base decision,
    only tighten it):
    - Injection + external-reach/scope-widening/unknown action → DENY.
    - Untrusted influence (even without a detected injection) on such an
      action → force CONFIRM (human gate), never silent allow.
    - Everything else → the base decision is returned unchanged.
    """
    action = str(action_type).strip()
    if base_decision == "deny":
        return BoundaryDecision("deny", "denied by permission kernel", action)
    external, widening, fail_closed_unknown = _resolve_reach(action, side_effect_level)
    gated = external or widening or fail_closed_unknown
    if gated and injection_detected:
        if widening:
            kind = "scope-widening"
        elif external:
            kind = "external-send"
        else:
            kind = "unverified (treated as external)"
        return BoundaryDecision(
            "deny",
            f"blocked: a {kind} action was influenced by injected content from an untrusted surface",
            action,
            forced_gate=True,
        )
    if gated and untrusted_influence:
        return BoundaryDecision(
            "confirm",
            "human approval required: action with external reach was influenced by untrusted content",
            action,
            forced_gate=True,
        )
    return BoundaryDecision(base_decision, "no untrusted-input escalation", action)


def boundary_notice(decision: BoundaryDecision) -> str:
    """User-facing one-liner for a forced gate/deny."""
    if decision.decision == "deny" and decision.forced_gate:
        return (
            "I won't do that automatically: it would send data out or change my permissions "
            "based on instructions inside content I read from an untrusted source (a web page, "
            "transcript, or document). If you actually want this, tell me directly."
        )
    if decision.decision == "confirm" and decision.forced_gate:
        return "This action was influenced by content I read elsewhere, so I need your explicit confirmation first."
    return ""
