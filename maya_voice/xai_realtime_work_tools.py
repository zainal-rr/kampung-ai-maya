from __future__ import annotations

import asyncio
import os

from maya_browser.browser_extension_bridge import extension_last_open_result, reset_extension_last_open_result
from maya_voice.artifact_manifest import create_or_get_manifest, get_manifest
from maya_voice.browser_runtime import (
    browser_bridge_preflight_isolated,
    browser_ping_timeout_seconds,
    browser_preflight_seconds,
    browser_timeout_seconds,
    completed_browser_facts,
    failed_browser_facts,
    run_browser_capability_isolated,
    strict_browser_mode,
)
from maya_voice.tool_results import (
    browser_result_failed,
    local_work_result_needs_clarification,
    sanitize_internal_language,
    tool_result_for_maya,
)
from maya_voice.verified_facts import facts_block, work_fact
from maya_voice.work_runtime import voice_work_context
from maya_voice.xai_voice_work import (
    complete_voice_work,
    create_voice_work,
    mark_voice_work_running,
    set_voice_work_phase,
    voice_work_cancel_requested,
)


async def run_voice_browser_skill(
    db_path: str,
    request: str,
    *,
    voice_session_id: str = "",
    short_ack: str = "",
    voice_work_id: str | None = None,
) -> str:
    work_id = voice_work_id or await create_voice_work(
        db_path,
        request,
        kind="browser",
        voice_session_id=voice_session_id,
        short_ack=short_ack,
    )
    await mark_voice_work_running(db_path, work_id)
    strict_browser = strict_browser_mode()
    await set_voice_work_phase(db_path, work_id, "preflight", "checking browser bridge")
    if strict_browser:
        preflight = await browser_bridge_preflight_isolated(
            wait_seconds=browser_preflight_seconds(),
            ping_timeout=browser_ping_timeout_seconds(),
        )
        if not preflight.get("ready"):
            facts = failed_browser_facts(preflight, work_id=work_id, reason_code="browser_bridge_unavailable")
            result = f"browser_bridge_unavailable: the Maya Chrome extension bridge is not ready.\n{facts}"
            await complete_voice_work(db_path, work_id, result=result, status="failed")
            return tool_result_for_maya(request, result, status="failed")
    if await voice_work_cancel_requested(db_path, work_id):
        result = "I cancelled that browser action before it opened anything."
        await complete_voice_work(db_path, work_id, result=result, status="cancelled")
        return tool_result_for_maya(request, result, status="cancelled")
    await set_voice_work_phase(db_path, work_id, "building", "browser work running")
    old_mode = os.environ.get("MAYA_BROWSER_MODE")
    try:
        reset_extension_last_open_result()
        if strict_browser:
            os.environ["MAYA_BROWSER_MODE"] = "extension_strict"
        result = await run_browser_capability_isolated(
            db_path,
            request,
            timeout=browser_timeout_seconds(),
        )
    except Exception as exc:
        reason = _browser_failure_reason(exc, strict_browser)
        facts = failed_browser_facts({}, work_id=work_id, reason_code=reason)
        result = f"{reason}: I could not finish the browser action: {exc or 'timed out'}\n{facts}"
        await complete_voice_work(db_path, work_id, result=result, status="failed")
        return tool_result_for_maya(request, result, status="failed")
    finally:
        if strict_browser:
            if old_mode is None:
                os.environ.pop("MAYA_BROWSER_MODE", None)
            else:
                os.environ["MAYA_BROWSER_MODE"] = old_mode
    return await _finish_browser_result(db_path, request, work_id, result, strict_browser)


async def start_maya_work(
    db_path: str,
    request: str,
    *,
    assistant=None,
    voice_session_id: str = "",
    short_ack: str = "",
    kind: str = "work",
    voice_work_id: str | None = None,
    tool_args: dict | None = None,
    channel: str = "imac",
) -> str:
    work_id = voice_work_id or await create_voice_work(
        db_path,
        request,
        kind=kind or "work",
        voice_session_id=voice_session_id,
        short_ack=short_ack,
    )
    await mark_voice_work_running(db_path, work_id)
    manifest = await create_or_get_manifest(
        db_path,
        work_id,
        request=request,
        args=tool_args or {"request": request},
        kind=kind or "work",
    )
    await set_voice_work_phase(db_path, work_id, "drafting", "local work running")
    if assistant is None:
        result = (
            "I started tracking this request, but the local work engine is not attached to this voice session.\n"
            + facts_block([work_fact(work_active=False, phase="failed", work_id=work_id)])
        )
        await complete_voice_work(db_path, work_id, result=result, status="failed")
        return tool_result_for_maya(request, result, status="failed")
    if await voice_work_cancel_requested(db_path, work_id):
        result = "I cancelled that work before starting it."
        await complete_voice_work(db_path, work_id, result=result, status="cancelled")
        return tool_result_for_maya(request, result, status="cancelled")
    try:
        with voice_work_context(db_path, work_id):
            result = await assistant.handle_text(request, channel=channel or "imac", speak_reply=False)
    except Exception as exc:
        result = (
            f"I could not finish that local work: {exc}\n"
            + facts_block([work_fact(work_active=False, phase="failed", work_id=work_id)])
        )
        await complete_voice_work(db_path, work_id, result=result, status="failed")
        return tool_result_for_maya(request, result, status="failed")
    return await _finish_work_result(db_path, request, work_id, result, assistant, manifest)


def _browser_failure_reason(exc: Exception, strict_browser: bool) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return "browser_tool_timeout"
    return "browser_bridge_unavailable" if strict_browser else "browser_action_failed"


async def _finish_browser_result(
    db_path: str,
    request: str,
    work_id: str,
    result: str,
    strict_browser: bool,
) -> str:
    cleaned = sanitize_internal_language(result)
    status = "failed" if browser_result_failed(cleaned) else "completed"
    last_open = extension_last_open_result()
    if strict_browser and not (last_open and bool(last_open.get("openedInMayaGroup"))):
        cleaned += "\nbrowser_group_verification_failed: the browser action did not verify a Maya-group tab."
        status = "failed"
    cleaned = cleaned + "\n" + completed_browser_facts(last_open=last_open, status=status, work_id=work_id)
    if await voice_work_cancel_requested(db_path, work_id):
        result = "I cancelled that browser action before delivering the result."
        await complete_voice_work(db_path, work_id, result=result, status="cancelled")
        return tool_result_for_maya(request, result, status="cancelled")
    await complete_voice_work(db_path, work_id, result=cleaned, status=status)
    return tool_result_for_maya(request, cleaned, status=status)


async def _finish_work_result(
    db_path: str,
    request: str,
    work_id: str,
    result: object,
    assistant,
    manifest: dict,
) -> str:
    cleaned = sanitize_internal_language(str(result or "").strip())
    if await voice_work_cancel_requested(db_path, work_id):
        result = "I cancelled that work before opening or delivering it."
        await complete_voice_work(db_path, work_id, result=result, status="cancelled")
        return tool_result_for_maya(request, result, status="cancelled")
    status = "needs_clarification" if local_work_result_needs_clarification(assistant, cleaned) else "completed"
    latest_manifest = await get_manifest(db_path, work_id) or manifest
    cleaned = cleaned + "\n" + facts_block([
        work_fact(work_active=False, phase="done" if status == "completed" else "failed", work_id=work_id),
        {
            "manifest_version": int((latest_manifest or {}).get("manifest_version") or 0),
            "captured_at": (latest_manifest or {}).get("updated_at") or "",
            "volatile": False,
        },
    ])
    await complete_voice_work(db_path, work_id, result=cleaned, status=status)
    return tool_result_for_maya(request, cleaned, status=status)
