from __future__ import annotations

import os

from cost_tracker import record_usage
from language_policy import language_instruction
from models import TheSenses
from xai_realtime_visual_context_tools import (
    active_context_tool,
    execute_visual_context_tool,
)
from xai_voice_handoff import save_voice_handoff_request
from xai_voice_state_tools import read_maya_state


GEMINI_TOOL_NAME = "answer_with_gemini"
MAYA_STATE_TOOL_NAME = "read_maya_state"
HANDOFF_TOOL_NAME = "handoff_to_maya_work_lane"


def voice_tools() -> list[dict]:
    tools = [
        gemini_voice_tool(),
        maya_state_tool(),
        active_context_tool(),
        handoff_tool(),
    ]
    return tools


async def execute_voice_tool(db_path: str, name: str, args: dict) -> str:
    question = str(args.get("question") or args.get("text") or "").strip()
    if name == GEMINI_TOOL_NAME:
        return await answer_with_gemini(db_path, question)
    if name == MAYA_STATE_TOOL_NAME:
        return await read_maya_state(db_path, question)
    if name == HANDOFF_TOOL_NAME:
        request = str(args.get("request") or question).strip()
        if not request:
            return "I need the exact request before I can hand it off."
        await save_voice_handoff_request(db_path, request)
        return "Handoff saved. Tell Zainal you will handle it outside the paid voice session now."
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
            "The tool returns Maya's answer written by Gemini for better Malay quality."
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


def handoff_tool() -> dict:
    return {
        "type": "function",
        "name": HANDOFF_TOOL_NAME,
        "description": (
            "Use this when Zainal asks for long work or tool work during live voice: documents, spreadsheets, "
            "PowerPoint, HTML apps, browser research, travel searches, file opening, project changes, coding, "
            "memory writes, or anything that should run through Maya's normal agents. Do not do that work inside "
            "Grok voice. Save the request for Maya's work lane, then tell Zainal the paid voice session can close "
            "while Maya handles it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The exact user request to hand off to Maya's normal work lane.",
                }
            },
            "required": ["request"],
        },
    }


async def answer_with_gemini(db_path: str, question: str) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "Gemini is not available right now."
    prompt = [
        {"role": "system", "content": "You are Maya. Answer in natural Malay or Manglish for iMac voice."},
        {"role": "system", "content": language_instruction(question)},
        {"role": "system", "content": "Use 2 to 5 spoken sentences. Do not use exclamation marks. Avoid dash symbols."},
        {"role": "user", "content": question},
    ]
    reply = await TheSenses(api_key).chat(prompt)
    await record_usage(db_path, "gemini_flash_text_calls", 1, "imac voice Malay or Manglish tool")
    return reply.strip() or "Saya tak dapat susun jawapan elok tadi."


def _question_schema(description: str) -> dict:
    return {
        "type": "object",
        "properties": {"question": {"type": "string", "description": description}},
        "required": ["question"],
    }
