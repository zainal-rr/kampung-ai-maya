import asyncio
import tempfile
from pathlib import Path

from artifact_file_state import record_artifact_fingerprint
from artifact_sessions import record_artifact_session
from artifact_steering import (
    apply_late_artifact_steers,
    create_artifact_steer_event,
    latest_steer_status_text,
)
from storage import init_db


class FakeAssistant:
    def __init__(self):
        self.requests = []

    async def handle_text(self, text, channel, speak_reply=False):
        self.requests.append((text, channel, speak_reply))
        return f"Done. I updated the file at /Users/zainalabidinjamal/Desktop/Maya/documents/fake-v2.docx."


async def _record(db_path: str, path: Path, artifact_type: str, topic: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"{artifact_type}:{topic}".encode("utf-8"))
    await record_artifact_session(db_path, "imac", artifact_type, path, topic)
    await record_artifact_fingerprint(db_path, path)


async def main():
    with tempfile.TemporaryDirectory(prefix="artifact-steering-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant()

        docx = Path(tmp) / "meraki-v1.docx"
        await _record(db_path, docx, "docx", "Meraki document")
        event_id = await create_artifact_steer_event(
            db_path,
            work_id="vw_doc",
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
        assert assistant.requests[-1][0] == "update the latest document to actually it is for my ED"
        assert "applied it to the current artifact" in result

        docx.write_bytes(b"user edited this file")
        event_id = await create_artifact_steer_event(
            db_path,
            work_id="vw_doc",
            artifact_type="docx",
            original_request="make a Word doc about Meraki",
            steer_text="add a short executive summary",
            timing="after_created",
        )
        await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id="vw_doc",
            voice_session_id="voice_1",
            original_request="make a Word doc about Meraki",
            steer_texts=["add a short executive summary"],
            event_ids=[event_id],
        )
        assert assistant.requests[-1][0] == "make a new version of that with add a short executive summary"

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
        await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id="vw_xlsx",
            voice_session_id="voice_1",
            original_request="make a travel budget Excel",
            steer_texts=["also include a notes column"],
            event_ids=[event_id],
        )
        assert assistant.requests[-1][0] == "update the latest document to also include a notes column"

        event_id = await create_artifact_steer_event(
            db_path,
            work_id="vw_xlsx",
            artifact_type="xlsx",
            original_request="make a travel budget Excel",
            steer_text="change the workbook into a comparison model",
            timing="running",
        )
        await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id="vw_xlsx",
            voice_session_id="voice_1",
            original_request="make a travel budget Excel",
            steer_texts=["change the workbook into a comparison model"],
            event_ids=[event_id],
        )
        assert assistant.requests[-1][0] == "make a new version of that with change the workbook into a comparison model"

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
        await apply_late_artifact_steers(
            db_path,
            assistant=assistant,
            work_id="vw_pptx",
            voice_session_id="voice_1",
            original_request="make a presentation about Meraki",
            steer_texts=["make it for executives"],
            event_ids=[event_id],
        )
        assert assistant.requests[-1][0] == "make a new version of that with make it for executives"
        status = await latest_steer_status_text(db_path)
        assert "Recent artifact steering" in status
        assert "applied" in status

    print("artifact_steering_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
