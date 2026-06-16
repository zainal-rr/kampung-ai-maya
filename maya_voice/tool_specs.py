from __future__ import annotations

from maya_voice.xai_realtime_visual_context_tools import active_context_tool


GEMINI_TOOL_NAME = "answer_with_gemini"
MAYA_STATE_TOOL_NAME = "read_maya_state"
HANDOFF_TOOL_NAME = "handoff_to_maya_work_lane"
BROWSER_TOOL_NAME = "run_browser_skill"
MAYA_WORK_TOOL_NAME = "start_maya_work"
REVISE_WORK_TOOL_NAME = "revise_maya_work"
CANCEL_WORK_TOOL_NAME = "cancel_maya_work"
CONFIRM_ACTION_TOOL_NAME = "confirm_action"


def voice_tools() -> list[dict]:
    return [
        gemini_voice_tool(),
        maya_state_tool(),
        active_context_tool(),
        browser_tool(),
        maya_work_tool(),
        revise_work_tool(),
        cancel_work_tool(),
        confirm_action_tool(),
    ]


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
            "browser actions. This tool is for browser operation that Maya has chosen as the intended next action, "
            "not background research for ordinary conversation. If the user appears to want conversation rather than "
            "browser operation, answer in voice or offer a lookup instead of calling this tool by habit. It runs "
            "immediately while the voice session remains available. Do not use this "
            "when Zainal is talking about a document, file name, Word/Excel/PowerPoint window, or an artifact that "
            "happens to contain a word like Google in its filename."
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
            "It starts Maya's local work immediately while the voice session remains available. Use it for artifact "
            "follow-ups such as document names, opening drafts, adding sections, executive summaries, or giving Zainal "
            "a draft even if QA did not call it final."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The full intended non-browser work request from Zainal, including corrections and clarifications.",
                },
                "artifact_type": {
                    "type": "string",
                    "enum": [
                        "auto",
                        "word_document",
                        "excel_workbook",
                        "powerpoint_deck",
                        "markdown_note",
                        "html_file",
                    ],
                    "description": (
                        "Use this when Zainal has semantically specified the artifact type, including by answering "
                        "a previous clarification. Leave as auto for non-artifact work."
                    ),
                },
                "artifact_topic": {
                    "type": "string",
                    "description": "The semantic topic/content for the artifact, if clearer than the raw request.",
                },
                "title": {
                    "type": "string",
                    "description": "A concise user-facing artifact title chosen by Maya. Do not use raw transcript text as the title.",
                },
                "topic": {
                    "type": "string",
                    "description": "Structured artifact topic if Maya has one.",
                },
                "audience": {
                    "type": "string",
                    "description": "Structured audience if Zainal specified one.",
                },
                "duration_days": {
                    "type": "integer",
                    "description": "Structured itinerary duration in days when Maya understands a day count.",
                },
                "source_turn_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional source turn ids that support this structured intent.",
                },
                "idempotency_key": {
                    "type": "string",
                    "description": "Optional stable key if this tool call is a retry of the same side-effecting request.",
                },
            },
            "required": ["request"],
        },
    }


def revise_work_tool() -> dict:
    return {
        "type": "function",
        "name": REVISE_WORK_TOOL_NAME,
        "description": (
            "Use this when Zainal wants to steer, revise, add context to, or change active Maya work that is already "
            "running or the latest artifact Maya just created. Maya decides whether the utterance is a revision; "
            "this tool only applies the revision mechanics."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "work_id": {
                    "type": "string",
                    "description": "Optional Maya work id. Leave empty only when exactly one work item is active.",
                },
                "instruction": {
                    "type": "string",
                    "description": "The full revision or steering instruction from Zainal.",
                },
                "manifest_patch": {
                    "type": "object",
                    "description": "Structured fields Maya wants to patch onto the artifact manifest, if any.",
                    "additionalProperties": True,
                },
                "content_revision": {
                    "type": "string",
                    "description": "Opaque prose revision to forward to the builder/model. Python must not interpret it.",
                },
                "patch_type": {
                    "type": "string",
                    "description": (
                        "Optional mechanical patch type for safe in-place policy, such as context_note or cell_comment. "
                        "Leave empty when unsure."
                    ),
                },
                "postcondition": {
                    "type": "object",
                    "description": (
                        "Optional saved-file proof target for the revision. Use section-scoped requirements for "
                        "concrete visible outcomes Maya expects after the edit. For completed Word documents, loose "
                        "strings anywhere in the document are not enough. For source links, use required_section_links "
                        "with the exact URL under the Sources heading, or include links in section_additions. Python "
                        "checks these mechanically and must not infer meaning from the prose. "
                        "For completed Word documents, this is effectively required: without it the tool returns "
                        "needs_structured_revision instead of claiming the edit worked."
                    ),
                    "properties": {
                        "required_headings": {"type": "array", "items": {"type": "string"}},
                        "required_strings": {"type": "array", "items": {"type": "string"}},
                        "required_section_strings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "heading": {"type": "string"},
                                    "values": {"type": "array", "items": {"type": "string"}},
                                },
                                "additionalProperties": True,
                            },
                        },
                        "required_section_links": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "heading": {"type": "string"},
                                    "urls": {"type": "array", "items": {"type": "string"}},
                                },
                                "additionalProperties": True,
                            },
                        },
                        "section_additions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "heading": {"type": "string"},
                                    "paragraphs": {"type": "array", "items": {"type": "string"}},
                                    "links": {"type": "array", "items": {"type": "string"}},
                                },
                                "additionalProperties": True,
                            },
                        },
                    },
                    "additionalProperties": True,
                },
                "expected_manifest_version": {
                    "type": "integer",
                    "description": "Manifest version Maya is revising from, for compare-and-swap.",
                },
                "idempotency_key": {
                    "type": "string",
                    "description": "Optional stable key if this revision tool call is retried.",
                },
            },
            "required": ["instruction"],
        },
    }


def cancel_work_tool() -> dict:
    return {
        "type": "function",
        "name": CANCEL_WORK_TOOL_NAME,
        "description": (
            "Use this when Zainal asks Maya to cancel, stop, or abandon active Maya work. "
            "Cancellation is cooperative: in-flight model or file calls may finish, but cancelled work must not open "
            "or deliver an artifact."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "work_id": {
                    "type": "string",
                    "description": "Optional Maya work id. Leave empty only when exactly one work item is active.",
                },
                "reason": {
                    "type": "string",
                    "description": "Short reason in Zainal's words, if available.",
                },
            },
            "required": [],
        },
    }


def confirm_action_tool() -> dict:
    return {
        "type": "function",
        "name": CONFIRM_ACTION_TOOL_NAME,
        "description": (
            "Use this only to answer a pending safety confirmation. Maya interprets Zainal's yes/no, then calls "
            "this tool with the exact pending action id and fingerprint. Python never parses spoken confirmation text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_id": {
                    "type": "string",
                    "description": "The pending action id Maya was given.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "True only when Zainal clearly approved this exact pending action.",
                },
                "action_fingerprint": {
                    "type": "string",
                    "description": "The action fingerprint Maya was given when asking for confirmation.",
                },
            },
            "required": ["action_id", "approved", "action_fingerprint"],
        },
    }


def _question_schema(description: str) -> dict:
    return {
        "type": "object",
        "properties": {"question": {"type": "string", "description": description}},
        "required": ["question"],
    }
