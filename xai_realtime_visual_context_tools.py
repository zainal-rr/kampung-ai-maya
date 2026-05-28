from __future__ import annotations

from active_context import inspect_active_context
from visual_workflow import VisualWorkflowRenderer


ACTIVE_CONTEXT_TOOL_NAME = "inspect_active_context"
VISUAL_WORKFLOW_TOOL_NAME = "create_visual_workflow"


def active_context_tool() -> dict:
    return {
        "type": "function",
        "name": ACTIVE_CONTEXT_TOOL_NAME,
        "description": (
            "Inspect the active iMac app context. Use when Zainal asks about this, here, selected text, "
            "a figure, a slide, a document passage, a browser passage, or what to click. "
            "This reads structured selection, active file content, Office documents, Markdown, and browser DOM first. "
            "Use this before any screen tool for document, spreadsheet, slide, Markdown, or browser page questions."
        ),
        "parameters": _question_schema("The user's question about the current iMac selection or visible context."),
    }


def visual_workflow_tool() -> dict:
    return {
        "type": "function",
        "name": VISUAL_WORKFLOW_TOOL_NAME,
        "description": (
            "Create a rendered visual workflow or architecture diagram. Use when Zainal asks to map an idea visually, "
            "make a workflow diagram, create an architecture diagram, or make a Mermaid visual."
        ),
        "parameters": _question_schema("The topic or idea to turn into a rendered visual workflow."),
    }


async def execute_visual_context_tool(db_path: str, name: str, question: str) -> str | None:
    if name == ACTIVE_CONTEXT_TOOL_NAME:
        return await inspect_active_context(db_path, question, allow_screen_fallback=True)
    if name == VISUAL_WORKFLOW_TOOL_NAME:
        return await create_visual_workflow(db_path, question)
    return None


async def create_visual_workflow(db_path: str, question: str) -> str:
    topic = question.strip() or "Maya workflow"
    result = await VisualWorkflowRenderer(db_path).create(topic)
    return (
        "Created rendered visual workflow.\n"
        f"source: {result.source_path}\n"
        f"visual: {result.visual_path}\n"
        f"renderer: {result.renderer}"
    )


def _question_schema(description: str) -> dict:
    return {
        "type": "object",
        "properties": {"question": {"type": "string", "description": description}},
        "required": ["question"],
    }
