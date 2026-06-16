from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

from openpyxl import Workbook

from maya_documents.artifact_builder import ArtifactBuilder
from maya_documents.artifact_quality_core import ArtifactQualityResult
from maya_documents.artifact_qa_governance import SEMANTIC, blocker
from maya_documents.artifact_sessions import active_artifact_session
from context_layers import init_context_layers_db
from document_actions import DocumentActionRouter
from everyday_commands import EverydayCommandRouter
from harness_artifact_store import init_harness_artifact_db
from harness_store import init_harness_db
from lesson_store import init_lesson_db
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import get_preference, init_db
from office_modern_files import create_docx


class FakeBridge:
    def __init__(self) -> None:
        self.opened: list[tuple[str, str | None]] = []

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened.append((path, app_name))


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artifact-gate-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
        old_artifact_attempts = os.environ.get("ARTIFACT_QA_MAX_ATTEMPTS")
        old_docx_attempts = os.environ.get("DOCX_QA_MAX_ATTEMPTS")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("ARTIFACT_QA_MAX_ATTEMPTS", None)
        os.environ.pop("DOCX_QA_MAX_ATTEMPTS", None)
        try:
            bridge = FakeBridge()
            router = DocumentActionRouter(db_path, workspace=Path(tmp) / "Maya", bridge=bridge)
            bad_draft = Path(tmp) / "bad.xlsx"
            bad_draft.write_text("rough draft placeholder", encoding="utf-8")
            direct_reply = await router._draft_with_issues(
                "Excel draft",
                bad_draft,
                "telegram",
                "Microsoft Excel",
                "REJECT: failed quality",
            )
            _require("[file:" in direct_reply, f"failed draft should expose saved draft path: {direct_reply}")
            _require("not calling it final" in direct_reply and "I saved the draft at" in direct_reply, f"failed draft should be explicit: {direct_reply}")
            _require(await get_preference(db_path, "maya_last_document_path") == str(bad_draft), "inspectable draft should become latest document")
            _require(await get_preference(db_path, "maya_last_draft_document_path") == str(bad_draft), "inspectable draft should remain marked as draft")
            session = await active_artifact_session(db_path, "telegram", str(bad_draft))
            _require(session is not None and session.path == str(bad_draft), "inspectable draft should become active artifact session")
            draft_reply = await EverydayCommandRouter(db_path).handle("give me the rough", "telegram")
            _require(draft_reply is not None and "[file:" in draft_reply, f"rough draft should attach: {draft_reply}")
            _require("bad.xlsx" in draft_reply, f"rough draft should reference failed draft: {draft_reply}")
            imac_reply = await router._draft_with_issues(
                "edited Word draft",
                bad_draft,
                "imac",
                "Microsoft Word",
                "semantic note only",
                attempts=1,
                topic="soft warning smoke",
            )
            _require("asked Microsoft Word to open it on the iMac" in imac_reply, f"iMac draft should open: {imac_reply}")
            _require("not calling it final" in imac_reply, f"iMac draft should be honest: {imac_reply}")
            _require(bridge.opened[-1] == (str(bad_draft), "Microsoft Word"), "iMac draft should use bridge opener")
            soft_doc = Path(tmp) / "soft.docx"
            create_docx(soft_doc, "Soft QA Smoke", [("Summary", ["This draft is usable but has a soft content note."])])
            soft_quality = ArtifactQualityResult(
                "docx",
                path=str(soft_doc),
                issue_details=[blocker("semantic.review", SEMANTIC, "content reviewer mentioned a path through the narrative")],
            )
            soft_result = await ArtifactBuilder(db_path, bridge)._finish(
                soft_doc,
                "soft qa smoke",
                soft_quality,
                "imac",
                "delivery_gate_smoke",
                "smoke",
                "Microsoft Word",
                "Done. I created a soft QA smoke doc.",
                "I opened the draft. There is one quality note, so I am not calling it final yet.",
                True,
            )
            _require("not calling it final" in soft_result.reply, f"soft QA draft should open honestly: {soft_result.reply}")
            _require(bridge.opened[-1] == (str(soft_doc), "Microsoft Word"), "soft QA draft should open on iMac")

            bad_doc = Path(tmp) / "bad-doc.docx"
            create_docx(bad_doc, "Bad Technical Guide", [("Summary", ["Too thin."])])
            bad_doc_result = await ArtifactBuilder(db_path).finish_docx(
                bad_doc,
                "router setup guide",
                "telegram",
                run_id="delivery_gate_smoke",
                source_tool="smoke",
                doc_kind="technical_guide",
            )
            _require(not bad_doc_result.quality.passed, "bad Word doc should fail QA")
            _require("checked bad-doc.docx with QA once" in bad_doc_result.reply, f"no-repair wording wrong: {bad_doc_result.reply}")
            _require("automatic repair path" in bad_doc_result.reply, f"no-repair path should be explicit: {bad_doc_result.reply}")
            _require("3 internal attempts" not in bad_doc_result.reply, f"no-repair path should not claim 3 attempts: {bad_doc_result.reply}")

            retry_doc = Path(tmp) / "retry-doc.docx"
            create_docx(retry_doc, "Retry Technical Guide", [("Summary", ["Too thin."])])
            rebuild_calls: list[int] = []

            async def still_bad(attempt: int, _quality: ArtifactQualityResult) -> None:
                rebuild_calls.append(attempt)

            retry_result = await ArtifactBuilder(db_path).finish_docx(
                retry_doc,
                "router setup guide",
                "telegram",
                run_id="delivery_gate_smoke",
                source_tool="smoke",
                doc_kind="technical_guide",
                rebuild=still_bad,
            )
            _require(not retry_result.quality.passed, "retry Word doc should still fail QA")
            _require(rebuild_calls == [2, 3], f"expected two rebuild calls after initial QA: {rebuild_calls}")
            _require("after 3 internal attempts" in retry_result.reply, f"retry wording should use actual attempts: {retry_result.reply}")

            path = Path(tmp) / "bad-workbook.xlsx"
            workbook = Workbook()
            workbook.active.title = "Sheet"
            workbook.active["A1"] = "not enough"
            workbook.save(path)
            result = await ArtifactBuilder(db_path).finish_xlsx(
                path,
                "Tokyo food budget tracker",
                "telegram",
                run_id="delivery_gate_smoke",
                source_tool="smoke",
                label="an editable Tokyo food budget tracker",
            )
            _require(not result.quality.passed, "bad workbook should fail QA")
            _require("[file:" not in result.reply, f"failed ArtifactBuilder result should not attach: {result.reply}")
            _require(await get_preference(db_path, "maya_last_document_path") == str(soft_doc), "failed ArtifactBuilder result should not replace latest inspectable draft")
            print("artifact_delivery_gate_smoke: ok")
        finally:
            _restore_env("ANTHROPIC_API_KEY", old_anthropic)
            _restore_env("ARTIFACT_QA_MAX_ATTEMPTS", old_artifact_attempts)
            _restore_env("DOCX_QA_MAX_ATTEMPTS", old_docx_attempts)


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_harness_db(db_path)
    await init_harness_artifact_db(db_path)


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
