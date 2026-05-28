from __future__ import annotations

import os

from cost_tracker import record_usage
from browser_task_step import browser_task_step
from language_policy import language_instruction
from models import TheSenses
from xai_realtime_visual_context_tools import (
    active_context_tool,
    execute_visual_context_tool,
)
from xai_realtime_document_tools import DESKTOP_FILE_TOOL_NAME, desktop_file_tool, execute_desktop_file_tool
from xai_voice_state_tools import read_maya_state


GEMINI_TOOL_NAME = "answer_with_gemini"
MAYA_STATE_TOOL_NAME = "read_maya_state"
BROWSER_TASK_STEP_TOOL_NAME = "browser_task_step"


def voice_tools() -> list[dict]:
    tools = [
        gemini_voice_tool(),
        maya_state_tool(),
        active_context_tool(),
        browser_task_step_tool(),
        desktop_file_tool(),
    ]
    return tools


async def execute_voice_tool(db_path: str, name: str, args: dict) -> str:
    question = str(args.get("question") or args.get("text") or "").strip()
    if name == GEMINI_TOOL_NAME:
        return await answer_with_gemini(db_path, question)
    if name == MAYA_STATE_TOOL_NAME:
        return await read_maya_state(db_path, question)
    if name == BROWSER_TASK_STEP_TOOL_NAME:
        return await browser_task_step(db_path, question)
    if name == DESKTOP_FILE_TOOL_NAME:
        return await execute_desktop_file_tool(db_path, str(args.get("request") or question))
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


def browser_task_step_tool() -> dict:
    return {
        "type": "function",
        "name": BROWSER_TASK_STEP_TOOL_NAME,
        "description": (
            "Perform one browser step on the iMac, such as opening Chrome, searching Google, searching Google Images, "
            "opening Google Flights, Booking.com, or Airbnb, "
            "attempting to fill structured travel parameters, clicking a visible priced flight/hotel/Airbnb selection, "
            "inspecting the page, or summarizing visible browser results. "
            "Never book, pay, log in, submit, or enter private details."
        ),
        "parameters": _question_schema("The browser step to perform."),
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
