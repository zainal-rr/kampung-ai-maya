from __future__ import annotations

import asyncio
import os

from cost_tracker import record_usage
from language_policy import language_instruction
from models import TheSenses
from xai_realtime_visual_context_tools import execute_visual_context_tool
from browser_extension_bridge import extension_last_open_result, reset_extension_last_open_result
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
    structured_work_request,
    tool_result_for_maya as _tool_result_for_maya,
)
from maya_voice.artifact_manifest import create_or_get_manifest
from maya_voice.artifact_manifest import get_manifest
from maya_voice.confirmation import confirm_action
from maya_voice.verified_facts import facts_block, work_fact
from maya_voice.tool_guard import empty_request_reason
from maya_voice.work_control import cancel_maya_work, revise_maya_work
from maya_voice.work_runtime import voice_work_context
from maya_voice.tool_specs import (
    BROWSER_TOOL_NAME,
    CANCEL_WORK_TOOL_NAME,
    CONFIRM_ACTION_TOOL_NAME,
    GEMINI_TOOL_NAME,
    HANDOFF_TOOL_NAME,
    MAYA_STATE_TOOL_NAME,
    MAYA_WORK_TOOL_NAME,
    REVISE_WORK_TOOL_NAME,
    voice_tools,
)
from xai_voice_work import (
    complete_voice_work,
    create_voice_work,
    mark_voice_work_running,
    set_voice_work_phase,
    voice_work_cancel_requested,
)
from xai_voice_state_tools import read_maya_state


async def execute_voice_tool(
    db_path: str,
    name: str,
    args: dict,
    *,
    assistant=None,
    voice_session_id: str = "",
    short_ack: str = "",
    work_kind: str = "",
    voice_work_id: str | None = None,
) -> str:
    question = str(args.get("question") or args.get("text") or "").strip()
    if name == GEMINI_TOOL_NAME:
        return await answer_with_gemini(db_path, question)
    if name == MAYA_STATE_TOOL_NAME:
        return await read_maya_state(db_path, question)
    if name == BROWSER_TOOL_NAME:
        request = str(args.get("request") or question).strip()
        if empty_request_reason(bool(request)):
            return _tool_result_for_maya(
                request,
                "empty_request",
                status="needs_clarification",
            )
        return await run_voice_browser_skill(
            db_path,
            request,
            voice_session_id=voice_session_id,
            short_ack=short_ack,
            voice_work_id=voice_work_id,
        )
    if name in {MAYA_WORK_TOOL_NAME, HANDOFF_TOOL_NAME}:
        request = structured_work_request(args, question)
        if empty_request_reason(bool(request)):
            return _tool_result_for_maya(
                request,
                "empty_request",
                status="needs_clarification",
            )
        return await start_maya_work(
            db_path,
            request,
            assistant=assistant,
            voice_session_id=voice_session_id,
            short_ack=short_ack,
            kind=work_kind or "work",
            voice_work_id=voice_work_id,
            tool_args=args,
        )
    if name == REVISE_WORK_TOOL_NAME:
        return await revise_maya_work(
            db_path,
            assistant=assistant,
            work_id=str(args.get("work_id") or "").strip(),
            voice_session_id=voice_session_id,
            instruction=str(args.get("instruction") or question).strip(),
            manifest_patch=args.get("manifest_patch") if isinstance(args.get("manifest_patch"), dict) else None,
            content_revision=str(args.get("content_revision") or "").strip(),
            patch_type=str(args.get("patch_type") or "").strip(),
            postcondition=args.get("postcondition") if isinstance(args.get("postcondition"), dict) else None,
            expected_manifest_version=args.get("expected_manifest_version"),
            channel="imac",
        )
    if name == CANCEL_WORK_TOOL_NAME:
        return await cancel_maya_work(
            db_path,
            work_id=str(args.get("work_id") or "").strip(),
            voice_session_id=voice_session_id,
            reason=str(args.get("reason") or question).strip(),
        )
    if name == CONFIRM_ACTION_TOOL_NAME:
        result = await confirm_action(
            db_path,
            action_id=str(args.get("action_id") or "").strip(),
            approved=bool(args.get("approved")),
            action_fingerprint_value=str(args.get("action_fingerprint") or "").strip(),
        )
        status = "completed" if result.get("status") == "approved" else "failed"
        return _tool_result_for_maya("confirm pending action", str(result), status=status)
    extra = await execute_visual_context_tool(db_path, name, question)
    if extra is not None:
        return extra
    return f"Unknown tool: {name}"


async def answer_with_gemini(db_path: str, question: str) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "Malay quality answering is not available right now."
    prompt = [
        {"role": "system", "content": "You are Maya. Answer in natural Malay or Manglish for iMac voice."},
        {"role": "system", "content": language_instruction(question)},
        {"role": "system", "content": "Use 2 to 5 spoken sentences. Do not use exclamation marks. Avoid dash symbols."},
        {"role": "user", "content": question},
    ]
    reply = await TheSenses(api_key).chat(prompt)
    await record_usage(db_path, "gemini_flash_text_calls", 1, "imac voice Malay or Manglish tool")
    return reply.strip() or "Saya tak dapat susun jawapan elok tadi."


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
            return _tool_result_for_maya(request, result, status="failed")
    if await voice_work_cancel_requested(db_path, work_id):
        result = "I cancelled that browser action before it opened anything."
        await complete_voice_work(db_path, work_id, result=result, status="cancelled")
        return _tool_result_for_maya(request, result, status="cancelled")
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
        reason = "browser_tool_timeout" if isinstance(exc, asyncio.TimeoutError) else ("browser_bridge_unavailable" if strict_browser else "browser_action_failed")
        facts = failed_browser_facts({}, work_id=work_id, reason_code=reason)
        result = f"{reason}: I could not finish the browser action: {exc or 'timed out'}\n{facts}"
        await complete_voice_work(db_path, work_id, result=result, status="failed")
        return _tool_result_for_maya(request, result, status="failed")
    finally:
        if strict_browser:
            if old_mode is None:
                os.environ.pop("MAYA_BROWSER_MODE", None)
            else:
                os.environ["MAYA_BROWSER_MODE"] = old_mode
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
        return _tool_result_for_maya(request, result, status="cancelled")
    await complete_voice_work(db_path, work_id, result=cleaned, status=status)
    return _tool_result_for_maya(request, cleaned, status=status)


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
        return _tool_result_for_maya(request, result, status="failed")
    if await voice_work_cancel_requested(db_path, work_id):
        result = "I cancelled that work before starting it."
        await complete_voice_work(db_path, work_id, result=result, status="cancelled")
        return _tool_result_for_maya(request, result, status="cancelled")
    try:
        with voice_work_context(db_path, work_id):
            result = await assistant.handle_text(request, channel="imac", speak_reply=False)
    except Exception as exc:
        result = (
            f"I could not finish that local work: {exc}\n"
            + facts_block([work_fact(work_active=False, phase="failed", work_id=work_id)])
        )
        await complete_voice_work(db_path, work_id, result=result, status="failed")
        return _tool_result_for_maya(request, result, status="failed")
    cleaned = sanitize_internal_language(str(result or "").strip())
    if await voice_work_cancel_requested(db_path, work_id):
        result = "I cancelled that work before opening or delivering it."
        await complete_voice_work(db_path, work_id, result=result, status="cancelled")
        return _tool_result_for_maya(request, result, status="cancelled")
    status = "needs_clarification" if local_work_result_needs_clarification(assistant, cleaned) else "completed"
    latest_manifest = await get_manifest(db_path, work_id) or manifest
    cleaned = (
        cleaned
        + "\n"
        + facts_block([
            work_fact(work_active=False, phase="done" if status == "completed" else "failed", work_id=work_id),
            {
                "manifest_version": int((latest_manifest or {}).get("manifest_version") or 0),
                "captured_at": (latest_manifest or {}).get("updated_at") or "",
                "volatile": False,
            },
        ])
    )
    await complete_voice_work(db_path, work_id, result=cleaned, status=status)
    return _tool_result_for_maya(request, cleaned, status=status)
