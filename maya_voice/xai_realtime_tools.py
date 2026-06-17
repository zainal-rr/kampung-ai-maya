from __future__ import annotations

from maya_voice.xai_realtime_visual_context_tools import execute_visual_context_tool
from maya_voice import xai_realtime_work_tools as _work_tools
from maya_voice.browser_runtime import browser_bridge_preflight_isolated, run_browser_capability_isolated
from maya_voice.tool_results import (
    structured_work_request,
    tool_result_for_maya as _tool_result_for_maya,
)
from maya_core.provenance import provenance_from_tool_args
from maya_voice.confirmation import confirm_action
from maya_voice.provenance_runtime import (
    effective_voice_provenance,
    gate_voice_action,
    remember_result_provenance,
)
from maya_voice.tool_guard import empty_request_reason
from maya_voice.work_control import cancel_maya_work, revise_maya_work
from maya_voice.tool_specs import (
    BROWSER_TOOL_NAME,
    CANCEL_WORK_TOOL_NAME,
    CONFIRM_ACTION_TOOL_NAME,
    FORGET_MEMORY_TOOL_NAME,
    GEMINI_TOOL_NAME,
    HANDOFF_TOOL_NAME,
    MAYA_STATE_TOOL_NAME,
    MAYA_WORK_TOOL_NAME,
    RECALL_MEMORY_TOOL_NAME,
    REVISE_WORK_TOOL_NAME,
    SAVE_MEMORY_TOOL_NAME,
    voice_tools,
)
from maya_voice.xai_voice_state_tools import read_maya_state
from maya_voice.xai_gemini_tool import answer_with_gemini
from maya_voice.xai_memory_tools import forget_voice_memory, recall_voice_memory, save_voice_memory


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
    if name == SAVE_MEMORY_TOOL_NAME:
        memory_text = str(args.get("memory_text") or question).strip()
        if empty_request_reason(bool(memory_text)):
            return _tool_result_for_maya("", "empty_request", status="needs_clarification")
        provenance = await effective_voice_provenance(db_path, args, voice_session_id=voice_session_id)
        return await save_voice_memory(db_path, memory_text, provenance=provenance)
    if name == RECALL_MEMORY_TOOL_NAME:
        query = str(args.get("query") or question).strip()
        if empty_request_reason(bool(query)):
            return _tool_result_for_maya("", "empty_request", status="needs_clarification")
        result = await recall_voice_memory(db_path, query)
        await remember_result_provenance(db_path, voice_session_id, result, source_kind="memory_recall")
        return result
    if name == FORGET_MEMORY_TOOL_NAME:
        query = str(args.get("query") or question).strip()
        if empty_request_reason(bool(query)):
            return _tool_result_for_maya("", "empty_request", status="needs_clarification")
        provenance = await effective_voice_provenance(db_path, args, voice_session_id=voice_session_id)
        gate = await gate_voice_action(
            db_path,
            request=query,
            tool_name=FORGET_MEMORY_TOOL_NAME,
            payload={"query": query},
            provenance=provenance,
            side_effect_level="delete",
        )
        if gate:
            return gate
        return await forget_voice_memory(db_path, query)
    if name == BROWSER_TOOL_NAME:
        request = str(args.get("request") or question).strip()
        if empty_request_reason(bool(request)):
            return _tool_result_for_maya(
                request,
                "empty_request",
                status="needs_clarification",
            )
        provenance = await effective_voice_provenance(db_path, args, voice_session_id=voice_session_id)
        gate = await gate_voice_action(
            db_path,
            request=request,
            tool_name=BROWSER_TOOL_NAME,
            payload={"request": request},
            provenance=provenance,
            side_effect_level="write",
        )
        if gate:
            return gate
        result = await run_voice_browser_skill(
            db_path,
            request,
            voice_session_id=voice_session_id,
            short_ack=short_ack,
            voice_work_id=voice_work_id,
        )
        await remember_result_provenance(db_path, voice_session_id, result, source_kind="browser_page")
        return result
    if name in {MAYA_WORK_TOOL_NAME, HANDOFF_TOOL_NAME}:
        request = structured_work_request(args, question)
        if empty_request_reason(bool(request)):
            return _tool_result_for_maya(
                request,
                "empty_request",
                status="needs_clarification",
            )
        provenance = await effective_voice_provenance(db_path, args, voice_session_id=voice_session_id)
        gate = await gate_voice_action(
            db_path,
            request=request,
            tool_name=MAYA_WORK_TOOL_NAME,
            payload={"request": request, "args": args},
            provenance=provenance,
            side_effect_level="write",
        )
        if gate:
            return gate
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
        instruction = str(args.get("instruction") or question).strip()
        provenance = await effective_voice_provenance(db_path, args, voice_session_id=voice_session_id)
        gate = await gate_voice_action(
            db_path,
            request=instruction,
            tool_name=REVISE_WORK_TOOL_NAME,
            payload={"instruction": instruction, "work_id": str(args.get("work_id") or "").strip()},
            provenance=provenance,
            side_effect_level="write",
        )
        if gate:
            return gate
        return await revise_maya_work(
            db_path,
            assistant=assistant,
            work_id=str(args.get("work_id") or "").strip(),
            voice_session_id=voice_session_id,
            instruction=instruction,
            manifest_patch=args.get("manifest_patch") if isinstance(args.get("manifest_patch"), dict) else None,
            content_revision=str(args.get("content_revision") or "").strip(),
            patch_type=str(args.get("patch_type") or "").strip(),
            postcondition=args.get("postcondition") if isinstance(args.get("postcondition"), dict) else None,
            expected_manifest_version=args.get("expected_manifest_version"),
            channel="imac",
        )
    if name == CANCEL_WORK_TOOL_NAME:
        reason = str(args.get("reason") or question).strip()
        provenance = await effective_voice_provenance(db_path, args, voice_session_id=voice_session_id)
        gate = await gate_voice_action(
            db_path,
            request=reason,
            tool_name=CANCEL_WORK_TOOL_NAME,
            payload={"work_id": str(args.get("work_id") or "").strip(), "reason": reason},
            provenance=provenance,
            side_effect_level="write",
        )
        if gate:
            return gate
        return await cancel_maya_work(
            db_path,
            work_id=str(args.get("work_id") or "").strip(),
            voice_session_id=voice_session_id,
            reason=reason,
        )
    if name == CONFIRM_ACTION_TOOL_NAME:
        provenance = provenance_from_tool_args(args, default_kind="unknown")
        result = await confirm_action(
            db_path,
            action_id=str(args.get("action_id") or "").strip(),
            approved=bool(args.get("approved")),
            action_fingerprint_value=str(args.get("action_fingerprint") or "").strip(),
            approver_provenance=provenance,
        )
        status = "completed" if result.get("status") == "approved" else "failed"
        return _tool_result_for_maya("confirm pending action", str(result), status=status)
    extra = await execute_visual_context_tool(db_path, name, question)
    if extra is not None:
        await remember_result_provenance(db_path, voice_session_id, extra)
        return extra
    return f"Unknown tool: {name}"


async def run_voice_browser_skill(*args, **kwargs) -> str:
    _work_tools.browser_bridge_preflight_isolated = browser_bridge_preflight_isolated
    _work_tools.run_browser_capability_isolated = run_browser_capability_isolated
    return await _work_tools.run_voice_browser_skill(*args, **kwargs)


start_maya_work = _work_tools.start_maya_work
