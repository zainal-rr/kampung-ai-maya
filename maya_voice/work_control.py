from __future__ import annotations

from datetime import datetime
from pathlib import Path

from artifact_steering import (
    apply_late_artifact_steers,
    create_artifact_steer_event,
)
from maya_voice.artifact_manifest import create_metadata_only_manifest, get_manifest, patch_manifest
from maya_voice.tool_results import tool_result_for_maya
from maya_voice.word_revision import has_docx_postcondition, has_scoped_docx_postcondition
from xai_voice_work import (
    ACTIVE_PHASES,
    increment_voice_work_revision,
    request_voice_work_cancel,
    resolve_latest_active_voice_work,
)
from maya_voice.work_resolution import resolve_voice_work_for_revision


REVISION_RESULT_CODES = {
    "edited_in_place",
    "created_v2",
    "needs_clarification",
    "needs_confirmation",
    "version_conflict",
    "manual_edit_detected",
    "hard_blocked",
    "missing_artifact",
    "unsupported_patch_type",
    "revision_not_applied",
    "needs_structured_revision",
}


async def revise_maya_work(
    db_path: str,
    *,
    assistant,
    work_id: str = "",
    voice_session_id: str = "",
    instruction: str = "",
    manifest_patch: dict | None = None,
    content_revision: str = "",
    patch_type: str = "",
    postcondition: dict | None = None,
    expected_manifest_version: int | None = None,
    channel: str = "imac",
) -> str:
    cleaned = " ".join((content_revision or instruction).strip().split())
    if not cleaned:
        return tool_result_for_maya(
            "revise active work",
            _revision_result("needs_clarification", "empty_instruction"),
            status="needs_clarification",
        )
    resolved = await resolve_voice_work_for_revision(
        db_path,
        work_id=work_id or None,
        voice_session_id=voice_session_id,
    )
    status = str(resolved.get("status") or "")
    if status == "needs_clarification":
        return tool_result_for_maya(
            cleaned,
            _revision_result(
                "needs_clarification",
                "More than one Maya work item is active. Ask Zainal which work to revise.",
            ),
            status="needs_clarification",
        )
    if status == "not_found":
        return tool_result_for_maya(
            cleaned,
            _revision_result("missing_artifact", "missing_artifact"),
            status="needs_clarification",
        )
    if status == "needs_confirmation":
        work = resolved.get("work") or {}
        path = str(work.get("artifact_path") or "").strip()
        name = Path(path).name if path else str(work.get("request") or "that artifact")
        return tool_result_for_maya(
            cleaned,
            _revision_result(
                "needs_confirmation",
                f"artifact: {name}\n"
                "This artifact is from a different voice session. Ask Zainal to confirm this is the file to revise before changing it.",
            ),
            status="needs_confirmation",
        )
    work = resolved.get("work") or {}
    if not str(work.get("artifact_path") or "").strip() and str(work.get("phase") or "") not in ACTIVE_PHASES:
        return tool_result_for_maya(
            cleaned,
            _revision_result("missing_artifact", "missing_artifact"),
            status="needs_clarification",
        )
    target_work_id = str(work.get("id") or work_id or "")
    phase = str(work.get("phase") or "")
    artifact_path = str(work.get("artifact_path") or "").strip()
    artifact_type = _artifact_type_for_work(work)
    manifest = await get_manifest(db_path, target_work_id)
    if not manifest and artifact_path:
        manifest = await create_metadata_only_manifest(
            db_path,
            target_work_id,
            artifact_path=artifact_path,
            artifact_type=artifact_type,
            request=str(work.get("request") or ""),
        )
    if not manifest:
        return tool_result_for_maya(
            cleaned,
            _revision_result("missing_artifact", "missing_artifact"),
            status="failed",
        )
    if artifact_path and phase not in ACTIVE_PHASES and not Path(artifact_path).exists():
        return tool_result_for_maya(
            cleaned,
            _revision_result("missing_artifact", "missing_artifact"),
            status="needs_clarification",
        )
    if _needs_completed_word_proof(artifact_type, artifact_path, phase, postcondition):
        return tool_result_for_maya(
            cleaned,
            _revision_result(
                "needs_structured_revision",
                "Completed Word revisions need scoped saved-file proof. Re-call revise_maya_work with a postcondition "
                "containing required_section_strings, required_section_links, or section_additions. "
                "For source links, include the exact URL under required_section_links for the Sources section.",
            ),
            status="needs_clarification",
        )
    patch_payload = _patch_with_postcondition(manifest, manifest_patch, postcondition)
    patch_result = await patch_manifest(
        db_path,
        target_work_id,
        manifest_patch=patch_payload,
        content_revision=cleaned,
        expected_manifest_version=_expected_version(expected_manifest_version),
    )
    if patch_result.get("status") == "version_conflict":
        return tool_result_for_maya(
            cleaned,
            _revision_result("version_conflict", "version_conflict"),
            status="needs_clarification",
        )
    if patch_result.get("status") != "ok":
        return tool_result_for_maya(
            cleaned,
            _revision_result(
                "hard_blocked",
                str(patch_result.get("reason_code") or "manifest_patch_failed"),
            ),
            status="failed",
        )
    event_id = await create_artifact_steer_event(
        db_path,
        work_id=target_work_id,
        voice_session_id=voice_session_id,
        artifact_type=artifact_type,
        original_request=str(work.get("request") or ""),
        steer_text=cleaned,
        timing=phase if phase in ACTIVE_PHASES else "after_created",
    )
    revision_count = await increment_voice_work_revision(db_path, target_work_id)
    if phase in ACTIVE_PHASES and not artifact_path:
        return tool_result_for_maya(
            cleaned,
            _revision_result(
                "edited_in_place",
                "Revision captured for active Maya work. "
                f"Revision count: {revision_count}. It will be folded into the work before the draft is generated.",
            ),
            status="completed",
        )
    if not assistant:
        return tool_result_for_maya(
            cleaned,
            _revision_result(
                "hard_blocked",
                "Revision captured, but the local work engine is not attached.",
            ),
            status="failed",
        )
    patch_type = patch_type.strip().lower() or _patch_type(manifest_patch)
    output = await apply_late_artifact_steers(
        db_path,
        assistant=assistant,
        work_id=target_work_id,
        voice_session_id=voice_session_id,
        original_request=str(work.get("request") or ""),
        steer_texts=[cleaned],
        event_ids=[event_id],
        patch_type=patch_type,
        postcondition=postcondition,
        channel=channel,
    )
    if "revision_result_code:" not in (output or ""):
        output = _revision_result("hard_blocked", output or "Revision captured without a result code.")
    return tool_result_for_maya(cleaned, output, status=_status_for_revision_output(output))


async def cancel_maya_work(
    db_path: str,
    *,
    work_id: str = "",
    voice_session_id: str = "",
    reason: str = "",
) -> str:
    resolved = await resolve_latest_active_voice_work(
        db_path,
        work_id=work_id or None,
        voice_session_id=voice_session_id,
    )
    status = str(resolved.get("status") or "")
    if status == "needs_clarification":
        return tool_result_for_maya(
            "cancel active work",
            "More than one Maya work item is active. Ask Zainal which work to cancel.",
            status="needs_clarification",
        )
    if status == "not_found":
        return tool_result_for_maya(
            "cancel active work",
            "No active Maya work item is running.",
            status="needs_clarification",
        )
    if status == "already_completed":
        return tool_result_for_maya(
            "cancel active work",
            "already_completed",
            status="already_completed",
        )
    work = resolved.get("work") or {}
    result = await request_voice_work_cancel(db_path, str(work.get("id") or ""), reason)
    return tool_result_for_maya(
        "cancel active work",
        f"Cancel requested. Phase: {result.get('phase', '')}.",
        status=str(result.get("status") or "completed"),
    )


def _artifact_type_for_work(work: dict) -> str:
    path = str(work.get("artifact_path") or "").strip()
    if path:
        suffix = Path(path).suffix.lower().lstrip(".")
        if suffix:
            return suffix
    request = str(work.get("request") or "").lower()
    if any(term in request for term in ("powerpoint", "presentation", "slides", "pptx", "deck")):
        return "pptx"
    if any(term in request for term in ("excel", "spreadsheet", "workbook", "xlsx")):
        return "xlsx"
    if any(term in request for term in ("word", "docx", "document", "doc file")):
        return "docx"
    return ""


def _patch_with_postcondition(manifest: dict, patch: dict | None, postcondition: dict | None) -> dict | None:
    if not postcondition:
        return patch
    payload = dict(patch or {})
    intent = dict(manifest.get("structured_intent") or {})
    existing = list(intent.get("revision_postconditions") or [])
    existing.append({"created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z", "postcondition": postcondition})
    payload["revision_postconditions"] = existing
    return payload


def _needs_completed_word_proof(artifact_type: str, artifact_path: str, phase: str, postcondition: dict | None) -> bool:
    if artifact_type != "docx" or not artifact_path:
        return False
    if phase in ACTIVE_PHASES:
        return False
    return not (has_docx_postcondition(postcondition) and has_scoped_docx_postcondition(postcondition))


def _expected_version(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _patch_type(manifest_patch: dict | None) -> str:
    if not isinstance(manifest_patch, dict):
        return ""
    return str(manifest_patch.get("patch_type") or manifest_patch.get("operation") or "").strip().lower()


def _revision_result(code: str, detail: str = "") -> str:
    if code not in REVISION_RESULT_CODES:
        code = "hard_blocked"
    detail = str(detail or "").strip()
    return f"revision_result_code: {code}" + (f"\n{detail}" if detail else "")


def _status_for_revision_output(output: str) -> str:
    code = ""
    for line in str(output or "").splitlines():
        if line.startswith("revision_result_code:"):
            code = line.split(":", 1)[1].strip()
            break
    if code in {"edited_in_place", "created_v2", "manual_edit_detected", "unsupported_patch_type"}:
        return "completed"
    if code in {
        "needs_clarification",
        "needs_confirmation",
        "version_conflict",
        "missing_artifact",
        "needs_structured_revision",
    }:
        return "needs_confirmation" if code == "needs_confirmation" else "needs_clarification"
    return "failed"
