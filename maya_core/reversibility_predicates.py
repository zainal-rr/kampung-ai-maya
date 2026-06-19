from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from maya_core.provenance import (
    OWNER_SOURCES,
    TRUSTED_INTERNAL_SOURCES,
    ProvenanceContext,
    ensure_provenance,
    normalize_source_kind,
)
from maya_core.safe_paths import resolve_safe_path
from maya_core.workspace_paths import is_workspace_path


TIER_R = "R"
TIER_R_CONDITIONAL = "R-C"
TIER_I = "I"

TIER_I_TOOLS = frozenset({
    "browser.click",
    "mcp.call",
    "repo.apply_patch",
    "telegram.send_file",
    "pptx.create",
    "skill.activate",
    "blender.create_model",
})

ARTIFACT_CREATE_TOOLS = frozenset({"file.create", "docx.create", "xlsx.create"})
MAYA_FIELD_SOURCES = frozenset({"maya_internal", "maya_derived", "trusted_internal"})
OWNER_OR_MAYA_FIELD_SOURCES = frozenset({
    "owner_literal",
    "owner_text",
    "owner_voice",
    *MAYA_FIELD_SOURCES,
})

PATH_CONTROL_FIELDS = (
    "path",
    "output_path",
    "destination_path",
    "filename",
    "file_name",
    "name",
    "title",
    "app",
    "target",
)
SHEET_CONTROL_FIELDS = ("sheet_name", "tab_name", "worksheet_name")
DELIVERY_FIELDS = (
    "recipient",
    "to",
    "email",
    "cc",
    "bcc",
    "share",
    "send",
    "deliver",
    "present",
    "upload",
    "destination",
    "output_media",
    "external_destination",
)
RISK_FLAGS = (
    "overwrite",
    "replace",
    "append",
    "open_after_create",
    "private_content",
    "contains_private_content",
    "disclosure",
    "remote_loads",
    "remote_media",
    "scripts",
    "macros",
    "external_links",
    "formula_remote_refs",
)


@dataclass(frozen=True)
class ReversibilityPredicateResult:
    allowed: bool
    tool_name: str
    tier: str
    reason: str


def can_relax_reversibility_friction(
    tool_name: str,
    args: Mapping[str, Any] | None = None,
    provenance: ProvenanceContext | Mapping[str, Any] | None = None,
    browser_context: Mapping[str, Any] | None = None,
    field_provenance: Mapping[str, Any] | None = None,
) -> ReversibilityPredicateResult:
    """Pure Step 3 predicate artifact.

    This does not authorize an action. It answers only whether the extra
    reversibility friction may relax for the locked v1 tool mapping. W7
    provenance, source-trust, disclosure, cost, and approval gates remain
    separate authorities.
    """
    name = str(tool_name or "").strip()
    data = dict(args or {})
    if name == "screen.capture":
        if _has_delivery_request(data):
            return _deny(name, TIER_R, "screen capture with delivery/disclosure request stays gated")
        return ReversibilityPredicateResult(True, name, TIER_R, "read-only local screen capture")
    if name == "browser.inspect":
        return is_current_page_browser_inspect(name, data, browser_context)
    if name in ARTIFACT_CREATE_TOOLS:
        return is_contained_artifact_create(name, data, provenance, field_provenance=field_provenance)
    if name == "memory.write":
        return is_owner_authored_memory_write(data, provenance)
    if name in TIER_I_TOOLS:
        return _deny(name, TIER_I, "Tier I in locked v1 mapping")
    return _deny(name, TIER_I, "unknown or unmapped tool defaults to Tier I")


def is_current_page_browser_inspect(
    tool_name: str,
    args: Mapping[str, Any] | None,
    browser_context: Mapping[str, Any] | None,
) -> ReversibilityPredicateResult:
    name = str(tool_name or "browser.inspect")
    data = dict(args or {})
    if any(_truthy(data.get(key)) for key in ("navigate", "open_url", "click", "submit", "download", "login")):
        return _deny(name, TIER_R_CONDITIONAL, "browser inspect includes a mutating or navigational request")
    url = str(data.get("url") or "").strip()
    if not url:
        return ReversibilityPredicateResult(True, name, TIER_R_CONDITIONAL, "inspect already-loaded current page")
    context = dict(browser_context or {})
    current_url = str(context.get("current_url") or "").strip()
    already_loaded = bool(context.get("already_loaded"))
    if already_loaded and current_url and url == current_url:
        return ReversibilityPredicateResult(True, name, TIER_R_CONDITIONAL, "inspect exact already-loaded current page")
    return _deny(name, TIER_R_CONDITIONAL, "URL navigation is not free-routed in v1")


def is_contained_artifact_create(
    tool_name: str,
    args: Mapping[str, Any] | None,
    provenance: ProvenanceContext | Mapping[str, Any] | None = None,
    *,
    field_provenance: Mapping[str, Any] | None = None,
) -> ReversibilityPredicateResult:
    del provenance  # trigger provenance is not enough to bless control targets.
    name = str(tool_name or "")
    data = dict(args or {})
    field_sources = dict(field_provenance or {})
    if name not in ARTIFACT_CREATE_TOOLS:
        return _deny(name, TIER_I, "not a v1 contained artifact tool")
    if _has_delivery_request(data):
        return _deny(name, TIER_R_CONDITIONAL, "artifact creation includes delivery/disclosure request")
    risky = _first_truthy(data, RISK_FLAGS)
    if risky:
        return _deny(name, TIER_R_CONDITIONAL, f"artifact creation risk flag requires gate: {risky}")

    for field in PATH_CONTROL_FIELDS:
        raw = data.get(field)
        if not _present(raw):
            continue
        if not _field_source_is_maya(field_sources, field):
            return _deny(name, TIER_R_CONDITIONAL, f"{field} must be Maya-derived before free-routing")
        if field in {"path", "output_path", "destination_path"}:
            path_decision = resolve_safe_path(str(raw), "write")
            if not path_decision.allowed or not path_decision.resolved:
                return _deny(name, TIER_R_CONDITIONAL, f"{field} is not inside Maya's safe path policy")
            if not is_workspace_path(path_decision.resolved):
                return _deny(name, TIER_R_CONDITIONAL, f"{field} is not inside Maya workspace")
            if path_decision.resolved.exists():
                return _deny(name, TIER_R_CONDITIONAL, f"{field} would overwrite an existing file")
        else:
            if not _safe_local_name(str(raw)):
                return _deny(name, TIER_R_CONDITIONAL, f"{field} is not a safe local name")

    if name == "xlsx.create":
        for field in SHEET_CONTROL_FIELDS:
            raw = data.get(field)
            if not _present(raw):
                continue
            if not _field_source_is_owner_or_maya(field_sources, field):
                return _deny(name, TIER_R_CONDITIONAL, f"{field} must be owner-literal or Maya-derived")
            if not _safe_sheet_name(str(raw)):
                return _deny(name, TIER_R_CONDITIONAL, f"{field} is not a safe sheet name")

    return ReversibilityPredicateResult(
        True,
        name,
        TIER_R_CONDITIONAL,
        "contained local artifact create with no untrusted control target",
    )


def is_owner_authored_memory_write(
    args: Mapping[str, Any] | None,
    provenance: ProvenanceContext | Mapping[str, Any] | None,
) -> ReversibilityPredicateResult:
    data = dict(args or {})
    if not _present(data.get("content")):
        return _deny("memory.write", TIER_R_CONDITIONAL, "memory content is missing")
    if any(_truthy(data.get(key)) for key in ("relayed", "from_untrusted", "derived_from_untrusted", "control_target")):
        return _deny("memory.write", TIER_R_CONDITIONAL, "memory write carries untrusted or control-target marker")
    prov = ensure_provenance(provenance or data.get("provenance"), default_kind="unknown")
    if prov.injection_detected or prov.untrusted_influence:
        return _deny("memory.write", TIER_R_CONDITIONAL, "memory provenance is untrusted or injection-influenced")
    if prov.source_kind not in OWNER_SOURCES and prov.source_kind not in TRUSTED_INTERNAL_SOURCES:
        return _deny("memory.write", TIER_R_CONDITIONAL, "memory write is not owner-authored or trusted-internal")
    return ReversibilityPredicateResult(True, "memory.write", TIER_R_CONDITIONAL, "owner-authored memory write")


def _deny(tool_name: str, tier: str, reason: str) -> ReversibilityPredicateResult:
    return ReversibilityPredicateResult(False, str(tool_name or "unknown"), tier, reason)


def _has_delivery_request(args: Mapping[str, Any]) -> bool:
    return any(_truthy(args.get(field)) for field in DELIVERY_FIELDS)


def _first_truthy(args: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        if _truthy(args.get(field)):
            return field
    return ""


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "none", "null"}
    return bool(value)


def _field_source_is_maya(field_provenance: Mapping[str, Any], field: str) -> bool:
    return _field_source(field_provenance, field) in MAYA_FIELD_SOURCES


def _field_source_is_owner_or_maya(field_provenance: Mapping[str, Any], field: str) -> bool:
    return _field_source(field_provenance, field) in OWNER_OR_MAYA_FIELD_SOURCES


def _field_source(field_provenance: Mapping[str, Any], field: str) -> str:
    """Return the independently computed source for a control field.

    The planner/tool-call payload is intentionally not inspected for
    ``path_source``/``field_sources`` style labels here. Those labels are
    planner-writable in the live loop. Step 3 wiring must pass a provenance map
    produced by Maya's trusted ledger/slugger layer.
    """
    if field in field_provenance:
        return _normalize_field_source(field_provenance[field])
    return "unknown"


def _normalize_field_source(value: Any) -> str:
    if isinstance(value, Mapping):
        return _source_from_provenance(value)
    text = str(value or "").strip().lower()
    if text in {"maya", "maya_generated", "maya-derived", "internal"}:
        return "maya_derived"
    if text in {"trusted_internal"}:
        return "maya_internal"
    if text in {"owner", "owner-literal", "user_literal", "user"}:
        return "owner_literal"
    kind = normalize_source_kind(text)
    return kind if kind != "unknown" else text or "unknown"


def _source_from_provenance(value: Any) -> str:
    prov = ensure_provenance(value, default_kind="unknown")
    if prov.untrusted_influence or prov.injection_detected:
        return "unknown"
    return prov.source_kind


def _safe_local_name(value: str) -> bool:
    text = value.strip()
    if not text or text in {".", ".."}:
        return False
    if "/" in text or "\\" in text or "\x00" in text:
        return False
    if Path(text).name != text:
        return False
    return True


def _safe_sheet_name(value: str) -> bool:
    text = value.strip()
    if not text or len(text) > 31:
        return False
    return not any(char in text for char in "[]:*?/\\")
