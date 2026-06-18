from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import asyncio
import sys as _w4_sys
import tempfile
from pathlib import Path
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_documents.document_request_parser import document_request
from maya_documents.artifact_preflight import ArtifactPreflight
from maya_documents.meet_artifact_context import append_current_meet_context_to_preflight
from maya_documents.meet_artifact_context import meet_artifact_extra_context_from_manifest
from maya_documents.meet_artifact_context import meet_artifact_title_from_manifest
from maya_core.storage import init_db
from maya_meet.artifact_handoff import build_meet_artifact_handoff, build_meet_revision_instruction
from maya_meet.actions import MeetingActionRunner
from maya_meet.engagement import meet_address_decision
from maya_meet.responder import _meeting_content_class
from maya_voice.artifact_manifest import create_or_get_manifest
from maya_voice.work_runtime import voice_work_context
from maya_voice.xai_voice_work import create_voice_work


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    asyncio.run(_run())
    print("meet_artifact_handoff_smoke: ok")


async def _run() -> None:
    context = (
        "We should meet at 3 pm.",
        "I think it will be hard because timing is tight.",
        "The next action is to prepare a short project update.",
    )
    addressed = meet_address_decision("Hello Maya. Hello Maya. Make a Word document about this")
    _require(addressed.addressed, str(addressed))
    _require(addressed.remainder.lower() == "make a word document about this", str(addressed))

    word = build_meet_artifact_handoff(
        addressed.remainder,
        action_class="draft",
        meeting_context_lines=context,
        session_id="m1",
    )
    _require(word is not None, "word handoff missing")
    _require(word.artifact_type == "docx", str(word))
    _require(word.tool_args["artifact_type"] == "word_document", str(word.tool_args))
    _require("hello maya" not in word.request.lower(), word.request)
    _require(word.request == "Create a Word document from the current meeting transcript.", word.request)
    _require("SOURCE MEETING TRANSCRIPT" not in word.request, word.request)
    _require("We should meet at 3 pm." not in word.request, word.request)
    parsed = document_request(word.request)
    _require(parsed is not None, word.request)
    _require(parsed[0] == "docx", str(parsed))
    _require("We should meet" not in parsed[1], str(parsed))
    extra_context = meet_artifact_extra_context_from_manifest({"structured_intent": word.tool_args})
    _require("Source meeting transcript" in extra_context, extra_context)
    _require("We should meet at 3 pm." in extra_context, extra_context)
    _require("timing is tight" in extra_context, extra_context)
    _require("Langkawi" not in word.request and "travel" not in word.request.lower(), word.request)
    _require("title" not in word.tool_args and "artifact_title" not in word.tool_args, str(word.tool_args))
    _require(word.tool_args["topic"] == "current meeting transcript", str(word.tool_args))
    _require(word.tool_args["meet_context_source"] == "current_meeting_transcript", str(word.tool_args))
    title = meet_artifact_title_from_manifest("# Meeting Summary\n\nBody", {"title": "current meeting transcript", "structured_intent": word.tool_args})
    _require(title == "We Should Meet At 3 Pm", title)
    explicit_title = meet_artifact_title_from_manifest("# Launch Readiness Checklist\n\nBody", {"title": "current meeting transcript", "structured_intent": word.tool_args})
    _require(explicit_title == "Launch Readiness Checklist", explicit_title)

    excel = build_meet_artifact_handoff(
        "make an Excel spreadsheet of the action items",
        action_class="draft",
        meeting_context_lines=context,
    )
    _require(excel is not None and excel.artifact_type == "xlsx", str(excel))
    _require(excel.tool_args["artifact_type"] == "excel_workbook", str(excel.tool_args))

    pptx = build_meet_artifact_handoff(
        "make a PPTX summary",
        action_class="draft",
        meeting_context_lines=context,
    )
    _require(pptx is not None and pptx.artifact_type == "pptx", str(pptx))
    _require(pptx.tool_args["artifact_type"] == "powerpoint_deck", str(pptx.tool_args))

    thin = build_meet_artifact_handoff(
        "make a Word document about this",
        action_class="draft",
        meeting_context_lines=[],
    )
    _require(thin is None, str(thin))
    vague = build_meet_artifact_handoff(
        "make a Word document about this meeting",
        action_class="draft",
        meeting_context_lines=("we should meet at 3pm", "i think because it will be hard"),
    )
    _require(vague is None, "vague meeting context should fail closed instead of drafting")
    filler = build_meet_artifact_handoff(
        "make a Word document about this meeting",
        action_class="draft",
        meeting_context_lines=("yeah", "okay", "sure"),
    )
    _require(filler is None, "filler-only meeting context should fail closed")

    revision = build_meet_revision_instruction(
        "revise the Word document with the last decision",
        meeting_context_lines=context,
    )
    _require(revision is not None, "revision context missing")
    _require("Use only this current meeting transcript" in revision, revision)
    _require("prepare a short project update" in revision, revision)
    _require(
        build_meet_revision_instruction("revise the Word document with the last decision", meeting_context_lines=())
        is None,
        "revision without context should fail closed",
    )
    _require(
        _meeting_content_class("My phone number is 017-555-1234.", "answer") == "owner_private",
        "contact details should not enter public meeting context",
    )
    await _runner_smoke(context)
    await _manifest_preflight_smoke(word.tool_args)


async def _runner_smoke(context: tuple[str, ...]) -> None:
    with tempfile.TemporaryDirectory(prefix="maya-meet-artifact-") as tmp:
        assistant = _FakeAssistant()
        runner = MeetingActionRunner(db_path=str(Path(tmp) / "meet.db"), assistant=assistant)
        result = await runner.run(
            request="make a Word document about this",
            action_class="draft",
            session_id="m1",
            meeting_context_lines=context,
        )
        _require(result.reason_code == "meeting_action_completed", str(result))
        _require(assistant.requests, "assistant did not receive work request")
        request, channel = assistant.requests[-1]
        _require(channel == "meet", channel)
        _require(request == "Create a Word document from the current meeting transcript.", request)
        _require("SOURCE MEETING TRANSCRIPT" not in request, request)
        _require("We should meet at 3 pm." not in request, request)
        _require("Langkawi" not in request and "travel" not in request.lower(), request)

        thin = await runner.run(
            request="make a Word document about this",
            action_class="draft",
            session_id="m1",
            meeting_context_lines=(),
        )
        _require(thin.reason_code == "meet_artifact_context_too_thin", str(thin))

        thin_revision = await runner.run(
            request="revise the Word document with the last decision",
            action_class="scratch_artifact",
            session_id="m1",
            meeting_context_lines=(),
        )
        _require(thin_revision.reason_code == "meet_artifact_context_too_thin", str(thin_revision))

        vague = await runner.run(
            request="make a Word document about this meeting",
            action_class="draft",
            session_id="m1",
            meeting_context_lines=("we should meet at 3pm", "i think because it will be hard"),
        )
        _require(vague.reason_code == "meet_artifact_context_too_thin", str(vague))


async def _manifest_preflight_smoke(tool_args: dict[str, object]) -> None:
    with tempfile.TemporaryDirectory(prefix="maya-meet-manifest-") as tmp:
        db_path = str(Path(tmp) / "meet.db")
        await init_db(db_path)
        work_id = await create_voice_work(db_path, "Create a Word document from the current meeting transcript.", kind="meet_artifact")
        await create_or_get_manifest(
            db_path,
            work_id or "",
            request="Create a Word document from the current meeting transcript.",
            args=tool_args,
            kind="meet_artifact",
        )
        base = ArtifactPreflight("docx", "current meeting transcript", "local", "Intent: draft meeting document.")
        with voice_work_context(db_path, work_id):
            scoped = await append_current_meet_context_to_preflight(base)
        _require("Source meeting transcript" in scoped.content, scoped.content)
        _require("We should meet at 3 pm." in scoped.content, scoped.content)
        _require("old context" in scoped.content, scoped.content)
        _require("Langkawi" not in scoped.content, scoped.content)


class _FakeAssistant:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    async def handle_text(self, text: str, channel: str, speak_reply: bool = False) -> str:
        self.requests.append((text, channel))
        return "Done. I created a scoped meeting artifact draft."


if __name__ == "__main__":
    main()
