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
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maya_voice.artifact_manifest import (
    apply_current_manifest_count_sections,
    create_or_get_manifest,
    get_manifest,
    patch_manifest,
    record_current_render_report_for_sections,
)
from maya_voice.confirmation import confirm_action, create_pending_confirmation
from maya_voice.tool_guard import empty_request_reason
from maya_voice.work_control import revise_maya_work
from maya_voice.work_runtime import voice_work_context
from storage import init_db
from xai_realtime_tools import MAYA_WORK_TOOL_NAME, execute_voice_tool
from xai_realtime_work_supervisor_smoke import FakeAssistant, FakeRealtimeSession
from xai_voice_work import complete_voice_work, create_voice_work, get_voice_work


async def _test_no_transcript_work_start() -> None:
    with tempfile.TemporaryDirectory(prefix="voice-seam-transcript-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        session = FakeRealtimeSession(db_path, FakeAssistant(db_path, tmp))
        await session._maybe_start_supervised_voice_work("Can you make me a")
        assert not session.supervised_voice_work_id
        assert session.function_call_tasks == set()


async def _test_empty_guard_is_behavioral() -> None:
    assert empty_request_reason(False) == "empty_request"
    outcomes = [
        empty_request_reason(bool(value))
        for value in ("Can you make me a", "asdfqwer", "build a site readiness brief for tomorrow")
    ]
    assert outcomes == ["", "", ""]


def _test_voice_prompt_contract() -> None:
    source = (ROOT / "voice_context.py").read_text("utf-8")
    assert "Only claim an outcome the tool result confirms" in source
    assert "Do not say it opened in the Maya group unless the result confirms it" in source
    assert "For simple answers, use 1 clear sentence" in source
    assert "Most replies should feel quick" in source
    assert "when Maya has semantically decided the next action is to operate the browser" in source
    assert "not merely because web research could make an answer richer" in source
    assert "If the user seems to want a conversational answer" in source
    assert "for 'tell me'" not in source
    assert "or 'recommend'" not in source
    assert "narrate from the selected or highlighted text first" in source


async def _test_manifest_boundary_and_cas() -> None:
    with tempfile.TemporaryDirectory(prefix="voice-manifest-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant(db_path, tmp)
        output = await execute_voice_tool(
            db_path,
            MAYA_WORK_TOOL_NAME,
            {
                "request": "make me a Word document about KL",
                "artifact_type": "word_document",
                "title": "KL Three Day Plan",
                "duration_days": 2,
            },
            assistant=assistant,
            voice_session_id="smoke",
        )
        assert "Status:" in output
        work = await _latest_work(db_path)
        assert work and work["id"]
        manifest = await get_manifest(db_path, str(work["id"]))
        assert manifest
        assert manifest["title"] == "KL Three Day Plan"
        assert manifest["structured_intent"]["duration_days"] == 2
        patched = await patch_manifest(
            db_path,
            str(work["id"]),
            manifest_patch={"duration_days": 3, "title": "KL Revised Plan"},
            content_revision="make it three days",
            expected_manifest_version=1,
        )
        assert patched["status"] == "ok"
        conflict = await patch_manifest(
            db_path,
            str(work["id"]),
            manifest_patch={"duration_days": 4},
            expected_manifest_version=1,
        )
        assert conflict["status"] == "version_conflict"


async def _test_render_report_count_mismatch() -> None:
    with tempfile.TemporaryDirectory(prefix="voice-render-report-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        work_id = await create_voice_work(db_path, "make a three-day doc", kind="document")
        await create_or_get_manifest(
            db_path,
            work_id or "",
            request="make a three-day doc",
            args={"title": "Three Day Plan", "duration_days": 3},
            kind="document",
        )
        path = Path(tmp) / "plan.docx"
        path.write_bytes(b"fake")
        with voice_work_context(db_path, work_id):
            report = await record_current_render_report_for_sections(
                path,
                [("Day 1 Plan", ["A"]), ("Day 2 Plan", ["B"])],
            )
        assert report["status"] == "failed"
        assert report["reason_code"] == "render_report_mismatch"


async def _test_count_sections_generated_from_manifest() -> None:
    with tempfile.TemporaryDirectory(prefix="voice-count-sections-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        work_id = await create_voice_work(db_path, "make a three-day doc", kind="document")
        await create_or_get_manifest(
            db_path,
            work_id or "",
            request="make a three-day doc",
            args={"title": "Three Day Plan", "duration_days": 3},
            kind="document",
        )
        path = Path(tmp) / "plan.docx"
        path.write_bytes(b"fake")
        with voice_work_context(db_path, work_id):
            sections = await apply_current_manifest_count_sections([("Day 1 Plan", ["A"]), ("Day 2 Plan", ["B"])])
            assert [title for title, _items in sections] == ["Day 1 Plan", "Day 2 Plan", "Day 3 Plan"]
            report = await record_current_render_report_for_sections(path, sections)
        assert report["status"] == "ok"


async def _test_confirmation_fingerprint_and_expiry() -> None:
    with tempfile.TemporaryDirectory(prefix="voice-confirm-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        pending = await create_pending_confirmation(
            db_path,
            action_id="send_1",
            summary="Send file",
            payload={"path": "/tmp/example.docx", "recipient": "telegram"},
            ttl_seconds=60,
        )
        ok = await confirm_action(
            db_path,
            action_id="send_1",
            approved=True,
            action_fingerprint_value=pending["action_fingerprint"],
        )
        assert ok["status"] == "approved"
        stale = await confirm_action(
            db_path,
            action_id="send_1",
            approved=True,
            action_fingerprint_value=pending["action_fingerprint"],
        )
        assert stale["reason_code"] == "stale_confirmation"
        pending2 = await create_pending_confirmation(
            db_path,
            action_id="send_2",
            summary="Send changed file",
            payload={"path": "/tmp/example-v2.docx", "recipient": "telegram"},
            ttl_seconds=60,
        )
        conflict = await confirm_action(
            db_path,
            action_id="send_2",
            approved=True,
            action_fingerprint_value="not-" + pending2["action_fingerprint"],
        )
        assert conflict["reason_code"] == "version_conflict"


async def _test_missing_manifest_revision_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="voice-missing-manifest-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        work_id = await create_voice_work(db_path, "make a doc", kind="document", voice_session_id="voice")
        output = await revise_maya_work(
            db_path,
            assistant=FakeAssistant(db_path, tmp),
            work_id=work_id or "",
            voice_session_id="voice",
            instruction="add summary",
        )
        assert "Status: failed" in output
        assert "revision_result_code: missing_artifact" in output


async def _test_completed_artifact_revision_metadata_manifest() -> None:
    with tempfile.TemporaryDirectory(prefix="voice-completed-revision-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        artifact = Path(tmp) / "office-network-v1.docx"
        artifact.write_bytes(b"fake docx")
        work_id = await create_voice_work(
            db_path,
            "make a Word document about office network setup",
            kind="document",
            voice_session_id="same",
        )
        await complete_voice_work(
            db_path,
            work_id,
            result=f"Done. I created a Word document at {artifact}.",
            status="completed",
            artifact_path=str(artifact),
        )
        output = await revise_maya_work(
            db_path,
            assistant=FakeAssistant(db_path, tmp),
            voice_session_id="same",
            instruction="add configuration prompts",
        )
        assert "Status: needs_clarification" in output
        assert "revision_result_code: needs_structured_revision" in output
        manifest = await get_manifest(db_path, work_id or "")
        assert manifest
        assert manifest["structured_intent"].get("metadata_only") is True
        assert manifest["structured_intent"].get("artifact_path") == str(artifact)
        assert "duration_days" not in manifest["structured_intent"]


async def _test_completed_artifact_missing_file_revision_code() -> None:
    with tempfile.TemporaryDirectory(prefix="voice-missing-artifact-revision-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        artifact = Path(tmp) / "missing.docx"
        work_id = await create_voice_work(
            db_path,
            "make a Word document that later disappears",
            kind="document",
            voice_session_id="same",
        )
        await complete_voice_work(
            db_path,
            work_id,
            result=f"Done. I created a Word document at {artifact}.",
            status="completed",
            artifact_path=str(artifact),
        )
        output = await revise_maya_work(
            db_path,
            assistant=FakeAssistant(db_path, tmp),
            voice_session_id="same",
            instruction="add a summary",
        )
        assert "Status: needs_clarification" in output
        assert "revision_result_code: missing_artifact" in output


async def _test_cross_session_revision_needs_confirmation() -> None:
    with tempfile.TemporaryDirectory(prefix="voice-cross-session-revision-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        artifact = Path(tmp) / "old-session.docx"
        artifact.write_bytes(b"fake docx")
        work_id = await create_voice_work(
            db_path,
            "make a Word document from old session",
            kind="document",
            voice_session_id="old",
        )
        await complete_voice_work(
            db_path,
            work_id,
            result=f"Done. I created a Word document at {artifact}.",
            status="completed",
            artifact_path=str(artifact),
        )
        output = await revise_maya_work(
            db_path,
            assistant=FakeAssistant(db_path, tmp),
            voice_session_id="new",
            instruction="add an executive summary",
        )
        assert "Status: needs_confirmation" in output
        assert "revision_result_code: needs_confirmation" in output
        assert artifact.stem in output
        explicit = await revise_maya_work(
            db_path,
            assistant=FakeAssistant(db_path, tmp),
            work_id=work_id or "",
            voice_session_id="new",
            instruction="add an appendix",
        )
        assert "Status: needs_confirmation" in explicit
        assert "revision_result_code: needs_confirmation" in explicit
        assert artifact.stem in explicit


async def _test_browser_strict_fails_closed() -> None:
    import xai_realtime_tools

    old_mode = os.environ.get("MAYA_BROWSER_MODE")
    old_wait = os.environ.get("MAYA_BROWSER_EXTENSION_WAIT_SECONDS")
    original_runner = xai_realtime_tools.run_browser_capability_isolated
    original_preflight = xai_realtime_tools.browser_bridge_preflight_isolated
    os.environ["MAYA_BROWSER_MODE"] = "extension_strict"
    os.environ["MAYA_BROWSER_EXTENSION_WAIT_SECONDS"] = "0"
    try:
        async def fake_runner(*_args, **_kwargs) -> str:
            raise AssertionError("browser runner must not execute when preflight fails")

        async def fake_preflight(**_kwargs):
            return {"ready": False, "client_connected": False, "reason_code": "browser_bridge_unavailable", "server_pid": 1234}

        xai_realtime_tools.run_browser_capability_isolated = fake_runner
        xai_realtime_tools.browser_bridge_preflight_isolated = fake_preflight
        with tempfile.TemporaryDirectory(prefix="voice-browser-strict-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            output = await execute_voice_tool(
                db_path,
                "run_browser_skill",
                {"request": "Google search modern kampung house"},
                voice_session_id="smoke",
            )
            assert "Status: failed" in output
            assert "browser_bridge_unavailable" in output
    finally:
        xai_realtime_tools.run_browser_capability_isolated = original_runner
        xai_realtime_tools.browser_bridge_preflight_isolated = original_preflight
        if old_mode is None:
            os.environ.pop("MAYA_BROWSER_MODE", None)
        else:
            os.environ["MAYA_BROWSER_MODE"] = old_mode
        if old_wait is None:
            os.environ.pop("MAYA_BROWSER_EXTENSION_WAIT_SECONDS", None)
        else:
            os.environ["MAYA_BROWSER_EXTENSION_WAIT_SECONDS"] = old_wait


async def _test_browser_strict_verified_group_facts() -> None:
    import xai_realtime_tools
    import maya_voice.browser_runtime as browser_runtime
    from browser_extension_bridge import remember_extension_open_result

    original_runner = xai_realtime_tools.run_browser_capability_isolated
    original_preflight = xai_realtime_tools.browser_bridge_preflight_isolated
    original_status = browser_runtime.extension_bridge_status
    try:
        async def fake_runner(_db_path: str, _request: str, *, timeout: float) -> str:
            remember_extension_open_result({
                "tabId": 42,
                "groupId": 7,
                "windowId": 9,
                "openedInMayaGroup": True,
                "url": "https://www.google.com/search?q=meraki",
                "title": "meraki - Google Search",
            })
            return "Google Search skill opened a Google search for: meraki"

        async def fake_preflight(**_kwargs):
            return {"ready": True, "client_connected": True, "reason_code": "connected", "server_pid": 1234}

        xai_realtime_tools.run_browser_capability_isolated = fake_runner
        xai_realtime_tools.browser_bridge_preflight_isolated = fake_preflight
        browser_runtime.extension_bridge_status = lambda: {"client_connected": True, "connected": True, "started": True, "port": 8975, "reason_code": "connected", "server_pid": 1234}
        with tempfile.TemporaryDirectory(prefix="voice-browser-group-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            output = await execute_voice_tool(
                db_path,
                "run_browser_skill",
                {"request": "Google search meraki"},
                voice_session_id="smoke",
            )
            assert "Status: completed" in output
            assert '"opened_in_maya_group": true' in output
            assert '"group_id": 7' in output
            assert '"window_id": 9' in output
    finally:
        xai_realtime_tools.run_browser_capability_isolated = original_runner
        xai_realtime_tools.browser_bridge_preflight_isolated = original_preflight
        browser_runtime.extension_bridge_status = original_status


async def _test_browser_strict_requires_group_proof() -> None:
    import xai_realtime_tools
    import maya_voice.browser_runtime as browser_runtime

    original_runner = xai_realtime_tools.run_browser_capability_isolated
    original_preflight = xai_realtime_tools.browser_bridge_preflight_isolated
    original_status = browser_runtime.extension_bridge_status
    try:
        async def fake_runner(_db_path: str, _request: str, *, timeout: float) -> str:
            return "Browser skill opened a Google search for: meraki"

        async def fake_preflight(**_kwargs):
            return {"ready": True, "client_connected": True, "reason_code": "connected", "server_pid": 1234}

        xai_realtime_tools.run_browser_capability_isolated = fake_runner
        xai_realtime_tools.browser_bridge_preflight_isolated = fake_preflight
        browser_runtime.extension_bridge_status = lambda: {"client_connected": True, "connected": True, "started": True, "port": 8975, "reason_code": "connected", "server_pid": 1234}
        with tempfile.TemporaryDirectory(prefix="voice-browser-no-proof-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            output = await execute_voice_tool(
                db_path,
                "run_browser_skill",
                {"request": "Google search meraki"},
                voice_session_id="smoke",
            )
            assert "Status: failed" in output
            assert "browser_group_verification_failed" in output
            assert '"opened_in_maya_group": false' in output
    finally:
        xai_realtime_tools.run_browser_capability_isolated = original_runner
        xai_realtime_tools.browser_bridge_preflight_isolated = original_preflight
        browser_runtime.extension_bridge_status = original_status


async def _latest_work(db_path: str) -> dict | None:
    import aiosqlite

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM voice_work_requests ORDER BY created_at DESC, id DESC LIMIT 1")
        row = await cursor.fetchone()
    return dict(row) if row else None


async def main() -> None:
    await _test_no_transcript_work_start()
    _test_voice_prompt_contract()
    await _test_empty_guard_is_behavioral()
    await _test_manifest_boundary_and_cas()
    await _test_render_report_count_mismatch()
    await _test_count_sections_generated_from_manifest()
    await _test_confirmation_fingerprint_and_expiry()
    await _test_missing_manifest_revision_fails()
    await _test_completed_artifact_revision_metadata_manifest()
    await _test_completed_artifact_missing_file_revision_code()
    await _test_cross_session_revision_needs_confirmation()
    await _test_browser_strict_fails_closed()
    await _test_browser_strict_verified_group_facts()
    await _test_browser_strict_requires_group_proof()
    print("voice_semantic_seam_manifest_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
