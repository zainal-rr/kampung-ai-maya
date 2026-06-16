# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

import asyncio
import tempfile
from pathlib import Path

from docx import Document

from maya_documents.artifact_file_state import record_artifact_fingerprint
from maya_documents.artifact_sessions import record_artifact_session
from maya_documents.artifact_steering import (
    apply_late_artifact_steers,
    create_artifact_steer_event,
    latest_steer_status_text,
)
from maya_voice.work_control import revise_maya_work
import maya_voice.work_resolution as work_resolution
from storage import get_preference
from storage import init_db
from xai_voice_work import complete_voice_work, create_voice_work


class FakeAssistant:
    def __init__(self, bridge=None, reply: str | None = None):
        self.requests = []
        self.documents = type("Docs", (), {"bridge": bridge})() if bridge else None
        self.reply = reply or "Done. I updated the file at /Users/zainalabidinjamal/Desktop/Maya/documents/fake-v2.docx."

    async def handle_text(self, text, channel, speak_reply=False):
        self.requests.append((text, channel, speak_reply))
        return self.reply


class FakeBridge:
    def __init__(self, *, unsaved: bool = False):
        self.opened = []
        self.unsaved = unsaved

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened.append((path, app_name))

    def _run_applescript(self, script: str) -> str:
        return "true" if self.unsaved else "false"


async def _record(db_path: str, path: Path, artifact_type: str, topic: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"{artifact_type}:{topic}".encode("utf-8"))
    await record_artifact_session(db_path, "imac", artifact_type, path, topic)
    await record_artifact_fingerprint(db_path, path)


async def _record_docx(db_path: str, path: Path, topic: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.add_heading("Bali Itinerary", level=0)
    doc.add_heading("Recommendations", level=1)
    doc.add_paragraph("Keep one flexible block for weather and traffic.")
    doc.save(path)
    await record_artifact_session(db_path, "imac", "docx", path, topic)
    await record_artifact_fingerprint(db_path, path)


async def main():
    with tempfile.TemporaryDirectory(prefix="artifact-steering-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant()

        docx = Path(tmp) / "meraki-v1.docx"
        await _record(db_path, docx, "docx", "Meraki document")
        work_id = await create_voice_work(db_path, "make a Word doc about Meraki", kind="document")
        await complete_voice_work(db_path, work_id, result="Created Meraki document.", artifact_path=str(docx))
        stale = Path(tmp) / "google-document-v2.docx"
        await _record(db_path, stale, "docx", "Stale Google document")
        event_id = await create_artifact_steer_event(
            db_path,
            work_id=work_id or "",
            artifact_type="docx",
            original_request="make a Word doc about Meraki",
            steer_text="actually it is for my ED",
            timing="running",
        )
        result = await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id="vw_doc",
            voice_session_id="voice_1",
            original_request="make a Word doc about Meraki",
            steer_texts=["actually it is for my ED"],
            event_ids=[event_id],
        )
        assert assistant.requests[-1][0] == "update that document to actually it is for my ED"
        assert await get_preference(db_path, "maya_last_document_path") == str(docx)
        assert "applied it to the current artifact" in result
        assert "revision_result_code: edited_in_place" in result

        docx.write_bytes(b"user edited this file")
        event_id = await create_artifact_steer_event(
            db_path,
            work_id="vw_doc",
            artifact_type="docx",
            original_request="make a Word doc about Meraki",
            steer_text="add a short executive summary",
            timing="after_created",
        )
        result = await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id="vw_doc",
            voice_session_id="voice_1",
            original_request="make a Word doc about Meraki",
            steer_texts=["add a short executive summary"],
            event_ids=[event_id],
        )
        assert assistant.requests[-1][0] == "make a new version of that document with add a short executive summary"
        assert "revision_result_code: manual_edit_detected" in result

        deleted = Path(tmp) / "deleted-v1.docx"
        await _record(db_path, deleted, "docx", "Deleted document")
        deleted_work_id = await create_voice_work(db_path, "make a Word doc about a deleted file", kind="document")
        await complete_voice_work(db_path, deleted_work_id, result="Created deleted document.", artifact_path=str(deleted))
        deleted.unlink()
        before_requests = len(assistant.requests)
        event_id = await create_artifact_steer_event(
            db_path,
            work_id=deleted_work_id or "",
            artifact_type="docx",
            original_request="make a Word doc about a deleted file",
            steer_text="add a note",
            timing="after_created",
        )
        result = await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id=deleted_work_id or "",
            voice_session_id="voice_1",
            original_request="make a Word doc about a deleted file",
            steer_texts=["add a note"],
            event_ids=[event_id],
        )
        assert "revision_result_code: missing_artifact" in result
        assert len(assistant.requests) == before_requests

        xlsx = Path(tmp) / "budget-v1.xlsx"
        await _record(db_path, xlsx, "xlsx", "Travel budget")
        event_id = await create_artifact_steer_event(
            db_path,
            work_id="vw_xlsx",
            artifact_type="xlsx",
            original_request="make a travel budget Excel",
            steer_text="also include a notes column",
            timing="running",
        )
        result = await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id="vw_xlsx",
            voice_session_id="voice_1",
            original_request="make a travel budget Excel",
            steer_texts=["also include a notes column"],
            event_ids=[event_id],
            patch_type="context_note",
        )
        assert assistant.requests[-1][0] == "update that document to also include a notes column"

        event_id = await create_artifact_steer_event(
            db_path,
            work_id="vw_xlsx",
            artifact_type="xlsx",
            original_request="make a travel budget Excel",
            steer_text="change the workbook into a comparison model",
            timing="running",
        )
        result = await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id="vw_xlsx",
            voice_session_id="voice_1",
            original_request="make a travel budget Excel",
            steer_texts=["change the workbook into a comparison model"],
            event_ids=[event_id],
        )
        assert assistant.requests[-1][0] == "make a new version of that document with change the workbook into a comparison model"
        assert "revision_result_code: unsupported_patch_type" in result

        pptx = Path(tmp) / "deck-v1.pptx"
        await _record(db_path, pptx, "pptx", "Board deck")
        event_id = await create_artifact_steer_event(
            db_path,
            work_id="vw_pptx",
            artifact_type="pptx",
            original_request="make a presentation about Meraki",
            steer_text="make it for executives",
            timing="running",
        )
        result = await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id="vw_pptx",
            voice_session_id="voice_1",
            original_request="make a presentation about Meraki",
            steer_texts=["make it for executives"],
            event_ids=[event_id],
        )
        assert assistant.requests[-1][0] == "make a new version of that document with make it for executives"
        assert "revision_result_code: created_v2" in result
        status = await latest_steer_status_text(db_path)
        assert "Recent artifact steering" in status
        assert "applied" in status

        bridge = FakeBridge()
        proof_assistant = FakeAssistant(bridge=bridge, reply="Done. I updated the latest Word document in place.")
        itinerary = Path(tmp) / "bali-itinerary-v1.docx"
        await _record_docx(db_path, itinerary, "Bali itinerary")
        proof_work_id = await create_voice_work(db_path, "make a Bali itinerary", kind="document")
        await complete_voice_work(db_path, proof_work_id, result="Created Bali itinerary.", artifact_path=str(itinerary))
        missing_proof = await revise_maya_work(
            db_path,
            assistant=proof_assistant,
            work_id=proof_work_id or "",
            voice_session_id="voice_2",
            instruction="add a Sources section with the Google link",
        )
        assert "revision_result_code: needs_structured_revision" in missing_proof
        assert not proof_assistant.requests
        weak_proof = await revise_maya_work(
            db_path,
            assistant=proof_assistant,
            work_id=proof_work_id or "",
            voice_session_id="voice_2",
            instruction="add a Sources section with the Google link",
            postcondition={"required_headings": ["Sources"], "required_strings": ["google.com/search"]},
        )
        assert "revision_result_code: needs_structured_revision" in weak_proof
        assert not proof_assistant.requests

        event_id = await create_artifact_steer_event(
            db_path,
            work_id=proof_work_id or "",
            artifact_type="docx",
            original_request="make a Bali itinerary",
            steer_text="add a Sources section with the Google link",
            timing="after_created",
        )
        google_link = "https://www.google.com/search?q=places+to+visit+in+Bali"
        result = await apply_late_artifact_steers(
            db_path,
            assistant=proof_assistant,
            work_id=proof_work_id or "",
            voice_session_id="voice_2",
            original_request="make a Bali itinerary",
            steer_texts=["add a Sources section with the Google link"],
            event_ids=[event_id],
            postcondition={
                "required_headings": ["Sources"],
                "required_section_links": [{"heading": "Sources", "urls": [google_link]}],
                "section_additions": [
                    {
                        "heading": "Sources",
                        "paragraphs": ["Google search for places to visit in Bali"],
                        "links": [google_link],
                    }
                ],
            },
        )
        final_text = "\n".join(paragraph.text for paragraph in Document(itinerary).paragraphs)
        assert "revision_result_code: edited_in_place" in result
        assert "Saved-file revision proof passed" in result
        assert "Sources" in final_text
        assert "Recommendations" in final_text
        assert bridge.opened[-1] == (str(itinerary), "Microsoft Word")
        assert _docx_has_hyperlink(itinerary, google_link)

        unsaved_bridge = FakeBridge(unsaved=True)
        unsaved_assistant = FakeAssistant(bridge=unsaved_bridge, reply="Done. I updated the latest Word document in place.")
        event_id = await create_artifact_steer_event(
            db_path,
            work_id=proof_work_id or "",
            artifact_type="docx",
            original_request="make a Bali itinerary",
            steer_text="add a warning note",
            timing="after_created",
        )
        result = await apply_late_artifact_steers(
            db_path,
            assistant=unsaved_assistant,
            work_id=proof_work_id or "",
            voice_session_id="voice_2",
            original_request="make a Bali itinerary",
            steer_texts=["add a warning note"],
            event_ids=[event_id],
        )
        assert unsaved_assistant.requests[-1][0] == "make a new version of that document with add a warning note"
        assert "revision_result_code: manual_edit_detected" in result

        invalid = Path(tmp) / "invalid-v1.docx"
        await _record(db_path, invalid, "docx", "Invalid document")
        invalid_work_id = await create_voice_work(db_path, "make an invalid document", kind="document")
        await complete_voice_work(db_path, invalid_work_id, result="Created invalid document.", artifact_path=str(invalid))
        event_id = await create_artifact_steer_event(
            db_path,
            work_id=invalid_work_id or "",
            artifact_type="docx",
            original_request="make an invalid document",
            steer_text="add a Sources section",
            timing="after_created",
        )
        result = await apply_late_artifact_steers(
            db_path,
            assistant=proof_assistant,
            work_id=invalid_work_id or "",
            voice_session_id="voice_2",
            original_request="make an invalid document",
            steer_texts=["add a Sources section"],
            event_ids=[event_id],
            postcondition={
                "required_section_links": [
                    {"heading": "Sources", "urls": ["https://www.google.com/search?q=missing"]}
                ]
            },
        )
        assert "revision_result_code: revision_not_applied" in result

        active_doc = Path(tmp) / "active-malaysia-v1.docx"
        stale_newer = Path(tmp) / "newer-other-session-v1.docx"
        await _record_docx(db_path, active_doc, "Active Malaysia")
        active_work_id = await create_voice_work(
            db_path,
            "make an active Malaysia document",
            kind="document",
            voice_session_id="old_session",
        )
        await complete_voice_work(db_path, active_work_id, result="Created active document.", artifact_path=str(active_doc))
        await _record_docx(db_path, stale_newer, "Newer stale document")
        stale_work_id = await create_voice_work(
            db_path,
            "make a newer unrelated document",
            kind="document",
            voice_session_id="newer_session",
        )
        await complete_voice_work(db_path, stale_work_id, result="Created newer document.", artifact_path=str(stale_newer))

        original_active_office_path = work_resolution._active_office_path

        async def fake_active_office_path(_db_path: str) -> str:
            return str(active_doc)

        work_resolution._active_office_path = fake_active_office_path
        try:
            active_link = "https://www.google.com/search?q=Langkawi+travel+guide"
            result = await revise_maya_work(
                db_path,
                assistant=proof_assistant,
                voice_session_id="current_voice_session",
                instruction="add a Sources section to the current active document",
                postcondition={
                    "required_section_links": [{"heading": "Sources", "urls": [active_link]}],
                    "section_additions": [{"heading": "Sources", "links": [active_link]}],
                },
            )
        finally:
            work_resolution._active_office_path = original_active_office_path

        assert "revision_result_code: edited_in_place" in result
        assert _docx_has_hyperlink(active_doc, active_link)
        assert not _docx_has_hyperlink(stale_newer, active_link)

        for suffix, artifact_type in (("xlsx", "xlsx"), ("pptx", "pptx")):
            active_office = Path(tmp) / f"active-office-v1.{suffix}"
            stale_office = Path(tmp) / f"newer-stale-v1.{suffix}"
            await _record(db_path, active_office, artifact_type, f"Active {artifact_type}")
            active_office_work_id = await create_voice_work(
                db_path,
                f"make an active {artifact_type} artifact",
                kind="document",
                voice_session_id=f"old_{artifact_type}",
            )
            await complete_voice_work(
                db_path,
                active_office_work_id,
                result=f"Created active {artifact_type}.",
                artifact_path=str(active_office),
            )
            await _record(db_path, stale_office, artifact_type, f"Newer stale {artifact_type}")
            stale_office_work_id = await create_voice_work(
                db_path,
                f"make a newer stale {artifact_type}",
                kind="document",
                voice_session_id=f"newer_{artifact_type}",
            )
            await complete_voice_work(
                db_path,
                stale_office_work_id,
                result=f"Created stale {artifact_type}.",
                artifact_path=str(stale_office),
            )

            async def fake_active_path(_db_path: str, path=str(active_office)) -> str:
                return path

            work_resolution._active_office_path = fake_active_path
            try:
                resolved = await work_resolution.resolve_voice_work_for_revision(
                    db_path,
                    voice_session_id="current_voice_session",
                )
            finally:
                work_resolution._active_office_path = original_active_office_path

            assert resolved["status"] == "ok"
            assert resolved["work"]["id"] == active_office_work_id
            assert resolved["work"]["artifact_path"] == str(active_office)

    print("artifact_steering_smoke: ok")


def _docx_has_hyperlink(path: Path, url: str) -> bool:
    doc = Document(path)
    for paragraph in doc.paragraphs:
        for hyperlink in paragraph._p.findall(".//w:hyperlink", paragraph._p.nsmap):
            rel_id = hyperlink.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            if rel_id and rel_id in paragraph.part.rels and paragraph.part.rels[rel_id].target_ref == url:
                return True
    return False


if __name__ == "__main__":
    asyncio.run(main())
