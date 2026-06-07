from __future__ import annotations

from document_actions_word_helpers import _document_edit_request
from document_actions import DocumentActionRouter
from route_tracker import record_route


DESKTOP_FILE_TOOL_NAME = "create_desktop_maya_file"


def desktop_file_tool() -> dict:
    return {
        "type": "function",
        "name": DESKTOP_FILE_TOOL_NAME,
        "description": (
            "Create a local Desktop Maya file and open it on the iMac. Use for Word, PowerPoint, "
            "Excel, Markdown, HTML, budget spreadsheets, and visual workflow files. "
            "For budget requests, create an Excel workbook. For generic travel budget requests, create a reusable "
            "single-sheet travel budget template. Use saved trip choices and call-mode participant count only when "
            "the request is explicitly for this trip/current trip/my trip or includes concrete trip details."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The file creation request, including file type and topic.",
                }
            },
            "required": ["request"],
        },
    }


async def execute_desktop_file_tool(db_path: str, request: str) -> str:
    text = _normalize_request(request)
    router = DocumentActionRouter(db_path)
    reply = await router.handle(text, "imac")
    if reply and router.last_model_lane:
        await record_route(
            db_path,
            "voice",
            f"create_desktop_maya_file + {router.last_model_lane}",
            "voice document workflow",
            router.last_cost_recorded,
        )
    return reply or "I could not identify the file type to create."


def _normalize_request(request: str) -> str:
    cleaned = " ".join(request.strip().split())
    if _document_edit_request(cleaned):
        return cleaned
    lowered = cleaned.lower()
    if any(word in lowered for word in ("budget", "budgeting", "expenses", "cost")) and not any(
        word in lowered for word in ("excel", "xlsx", "spreadsheet", "sheet")
    ):
        return f"make an Excel budget tracker for {cleaned}"
    if lowered.startswith(("do ", "build ", "prepare ", "generate ")):
        if "excel" in lowered or "spreadsheet" in lowered or "sheet" in lowered:
            return f"make an Excel spreadsheet about {cleaned}"
    return cleaned
