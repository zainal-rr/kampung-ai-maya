from __future__ import annotations

import os

from cost_tracker import record_usage
from language_policy import language_instruction
from models import TheSenses
from xai_realtime_visual_context_tools import (
    active_context_tool,
    execute_visual_context_tool,
)
from browser_capability import run_browser_capability
from xai_voice_work import complete_voice_work, create_voice_work, mark_voice_work_running
from xai_voice_state_tools import read_maya_state


GEMINI_TOOL_NAME = "answer_with_gemini"
MAYA_STATE_TOOL_NAME = "read_maya_state"
HANDOFF_TOOL_NAME = "handoff_to_maya_work_lane"
BROWSER_TOOL_NAME = "run_browser_skill"
MAYA_WORK_TOOL_NAME = "start_maya_work"


def voice_tools() -> list[dict]:
    tools = [
        gemini_voice_tool(),
        maya_state_tool(),
        active_context_tool(),
        browser_tool(),
        maya_work_tool(),
    ]
    return tools


async def execute_voice_tool(
    db_path: str,
    name: str,
    args: dict,
    *,
    assistant=None,
    voice_session_id: str = "",
    short_ack: str = "",
    work_kind: str = "",
) -> str:
    question = str(args.get("question") or args.get("text") or "").strip()
    if name == GEMINI_TOOL_NAME:
        return await answer_with_gemini(db_path, question)
    if name == MAYA_STATE_TOOL_NAME:
        return await read_maya_state(db_path, question)
    if name == BROWSER_TOOL_NAME:
        request = str(args.get("request") or question).strip()
        return await run_voice_browser_skill(db_path, request, voice_session_id=voice_session_id, short_ack=short_ack)
    if name in {MAYA_WORK_TOOL_NAME, HANDOFF_TOOL_NAME}:
        request = str(args.get("request") or question).strip()
        if not request:
            return "I need the exact request first."
        return await start_maya_work(
            db_path,
            request,
            assistant=assistant,
            voice_session_id=voice_session_id,
            short_ack=short_ack,
            kind=work_kind or "work",
        )
    extra = await execute_visual_context_tool(db_path, name, question)
    if extra is not None:
        return extra
    return f"Unknown tool: {name}"


def gemini_voice_tool() -> dict:
    return {
        "type": "function",
        "name": GEMINI_TOOL_NAME,
        "description": (
            "Use this for any Malay or Manglish user request, or when the user asks to answer in Malay. "
            "The tool returns Maya's answer with better Malay quality."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The user's latest Malay or Manglish question or request.",
                }
            },
            "required": ["question"],
        },
    }


def maya_state_tool() -> dict:
    return {
        "type": "function",
        "name": MAYA_STATE_TOOL_NAME,
        "description": (
            "Read Maya's local state such as status, cost, route, tasks, approvals, artifacts, "
            "daily focus, and project cockpit."
        ),
        "parameters": _question_schema("The user's question about Maya state."),
    }


def browser_tool() -> dict:
    return {
        "type": "function",
        "name": BROWSER_TOOL_NAME,
        "description": (
            "Use this for iMac browser work during live voice. It can open Chrome, Google Search, Google Images, "
            "Google Flights, YouTube, Reddit, Google Cloud, Booking.com, Airbnb, frequent sites, and safe visible "
            "browser actions. It runs immediately while the voice session remains available."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The exact browser request from Zainal.",
                }
            },
            "required": ["request"],
        },
    }


def maya_work_tool() -> dict:
    return {
        "type": "function",
        "name": MAYA_WORK_TOOL_NAME,
        "description": (
            "Use this for longer non-browser iMac work during live voice: documents, spreadsheets, PowerPoint, "
            "Markdown, visual workflows, memory writes, project work, coding requests, and file actions. "
            "It starts Maya's local work immediately while the voice session remains available."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The exact non-browser work request from Zainal.",
                }
            },
            "required": ["request"],
        },
    }


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
) -> str:
    work_id = await create_voice_work(
        db_path,
        request,
        kind="browser",
        voice_session_id=voice_session_id,
        short_ack=short_ack,
    )
    await mark_voice_work_running(db_path, work_id)
    try:
        result = await run_browser_capability(db_path, request)
    except Exception as exc:
        result = f"I could not finish the browser action: {exc}"
        await complete_voice_work(db_path, work_id, result=result, status="failed")
        return _tool_result_for_maya(request, result, status="failed")
    cleaned = _sanitize_internal_language(result)
    await complete_voice_work(db_path, work_id, result=cleaned, status="completed")
    return _tool_result_for_maya(request, cleaned)


async def start_maya_work(
    db_path: str,
    request: str,
    *,
    assistant=None,
    voice_session_id: str = "",
    short_ack: str = "",
    kind: str = "work",
) -> str:
    work_id = await create_voice_work(
        db_path,
        request,
        kind=kind or "work",
        voice_session_id=voice_session_id,
        short_ack=short_ack,
    )
    await mark_voice_work_running(db_path, work_id)
    if assistant is None:
        result = "I started tracking this request, but the local work engine is not attached to this voice session."
        await complete_voice_work(db_path, work_id, result=result, status="failed")
        return _tool_result_for_maya(request, result, status="failed")
    try:
        result = await assistant.handle_text(request, channel="imac", speak_reply=False)
    except Exception as exc:
        result = f"I could not finish that local work: {exc}"
        await complete_voice_work(db_path, work_id, result=result, status="failed")
        return _tool_result_for_maya(request, result, status="failed")
    cleaned = _sanitize_internal_language(str(result or "").strip())
    await complete_voice_work(db_path, work_id, result=cleaned, status="completed")
    return _tool_result_for_maya(request, cleaned)


def _tool_result_for_maya(request: str, result: str, *, status: str = "completed") -> str:
    return (
        f"Request: {request}\n"
        f"Status: {status}\n"
        "Use this result to answer Zainal as Maya. Do not mention internal architecture details.\n"
        f"Result:\n{result}"
    )


def _sanitize_internal_language(text: str) -> str:
    replacements = {
        "Browser skill ": "",
        "Google Search skill ": "Google Search ",
        "Google Images skill ": "Google Images ",
        "YouTube Research skill ": "YouTube ",
        "Reddit Research skill ": "Reddit ",
        "Google Cloud Console skill ": "Google Cloud Console ",
        "Maya's work lane": "Maya",
        "normal work lane": "Maya",
        "worker lane": "Maya",
        "handoff": "work request",
        "Handoff": "Work request",
        "paid voice session": "voice session",
        "Gemini": "Maya",
        "Claude": "Maya",
        "Artisan": "Maya",
    }
    cleaned = text
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned.strip()


def _question_schema(description: str) -> dict:
    return {
        "type": "object",
        "properties": {"question": {"type": "string", "description": description}},
        "required": ["question"],
    }
