from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from created_file_opener import open_created_file
from maya_voice.artifact_manifest import get_manifest, record_render_report
from maya_voice.word_revision import (
    apply_docx_postcondition,
    docx_headings,
    has_docx_postcondition,
    normalize_docx_postcondition,
    verify_docx_postcondition,
)


async def verify_revision_postcondition(
    db_path: str,
    *,
    work_id: str,
    artifact_path: str,
    artifact_type: str,
    postcondition: dict[str, Any] | None,
) -> dict[str, str]:
    if artifact_type != "docx" or not has_docx_postcondition(postcondition):
        return {"status": "skipped", "note": ""}
    path = Path(artifact_path)
    try:
        await asyncio.to_thread(apply_docx_postcondition, path, postcondition)
        verification = await asyncio.to_thread(verify_docx_postcondition, path, postcondition)
    except Exception as exc:
        await record_revision_report(
            db_path,
            work_id=work_id,
            path=path,
            postcondition=postcondition,
            status="failed",
            reason_code="postcondition_check_failed",
        )
        return {"status": "failed", "detail": f"I tried the revision, but could not verify the saved Word file: {exc}"}
    report = await record_revision_report(
        db_path,
        work_id=work_id,
        path=path,
        postcondition=postcondition,
        verification=verification,
        status="ok" if verification.get("passed") else "failed",
        reason_code="" if verification.get("passed") else "revision_postcondition_missing",
    )
    if not verification.get("passed"):
        missing = []
        if verification.get("missing_headings"):
            missing.append("missing headings: " + ", ".join(verification["missing_headings"]))
        if verification.get("missing_strings"):
            missing.append("missing text: " + ", ".join(verification["missing_strings"]))
        if verification.get("missing_section_strings"):
            missing.append("missing section text: " + ", ".join(verification["missing_section_strings"]))
        if verification.get("missing_section_links"):
            missing.append("missing section links: " + ", ".join(verification["missing_section_links"]))
        detail = "; ".join(missing) or "required saved-file proof was missing"
        return {"status": "failed", "detail": f"I tried the revision, but the saved document still failed verification: {detail}."}
    return {
        "status": "ok",
        "note": f"Saved-file revision proof passed. Render report {report.get('id', '')} recorded.",
    }


async def record_revision_report(
    db_path: str,
    *,
    work_id: str,
    path: Path,
    postcondition: dict[str, Any] | None,
    verification: dict[str, Any] | None = None,
    status: str,
    reason_code: str,
) -> dict[str, Any]:
    manifest = await get_manifest(db_path, work_id)
    version = int((manifest or {}).get("manifest_version") or 0)
    condition = normalize_docx_postcondition(postcondition)
    fields = {
        "revision_postcondition": {
            "required_headings": condition["required_headings"],
            "required_strings": condition["required_strings"],
            "required_section_strings": condition["required_section_strings"],
            "required_section_links": condition["required_section_links"],
            "missing_headings": list((verification or {}).get("missing_headings") or []),
            "missing_strings": list((verification or {}).get("missing_strings") or []),
            "missing_section_strings": list((verification or {}).get("missing_section_strings") or []),
            "missing_section_links": list((verification or {}).get("missing_section_links") or []),
        }
    }
    try:
        headings = await asyncio.to_thread(docx_headings, path)
    except Exception:
        headings = []
    return await record_render_report(
        db_path,
        work_id=work_id,
        manifest_version_used=version,
        artifact_path=str(path),
        fields_rendered=fields,
        sections_created=headings,
        status=status,
        reason_code=reason_code,
    )


async def reopen_revised_artifact(assistant, path: Path, artifact_type: str, channel: str) -> str:
    if channel != "imac":
        return ""
    app_name = {
        "docx": "Microsoft Word",
        "xlsx": "Microsoft Excel",
        "pptx": "Microsoft PowerPoint",
    }.get(artifact_type)
    bridge = _assistant_bridge(assistant)
    if bridge is None:
        return ""
    try:
        opened = await asyncio.to_thread(open_created_file, path, bridge, app_name)
    except Exception as exc:
        return f"I updated the saved file, but I could not reopen it on the iMac: {exc}"
    opened_name = opened or app_name or "the associated app"
    return f"I saved the revision and verified {opened_name} reopened the updated file on the iMac."


async def word_open_with_unsaved_changes(assistant, path: Path) -> bool:
    bridge = _assistant_bridge(assistant)
    if bridge is None or not hasattr(bridge, "_run_applescript"):
        return False
    return await asyncio.to_thread(_word_open_with_unsaved_changes_sync, bridge, path)


def _assistant_bridge(assistant):
    documents = getattr(assistant, "documents", None)
    if documents is not None and getattr(documents, "bridge", None) is not None:
        return documents.bridge
    return getattr(assistant, "bridge", None)


def _word_open_with_unsaved_changes_sync(bridge, path: Path) -> bool:
    safe_path = str(path).replace("\\", "\\\\").replace('"', '\\"')
    script = (
        'set targetPath to "' + safe_path + '"\n'
        'set changedFlag to "false"\n'
        'try\n'
        'tell application "Microsoft Word"\n'
        'repeat with d in documents\n'
        'set docPath to ""\n'
        'try\n'
        'set docPath to POSIX path of (full name of d as alias)\n'
        'end try\n'
        'if docPath is targetPath then\n'
        'if saved of d is false then set changedFlag to "true"\n'
        'end if\n'
        'end repeat\n'
        'end tell\n'
        'end try\n'
        'return changedFlag\n'
    )
    try:
        return str(bridge._run_applescript(script)).strip().lower() == "true"
    except Exception:
        return False
