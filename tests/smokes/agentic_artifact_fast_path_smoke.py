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

from harness_helpers.graph_runner import HarnessGraphRunner
from maya_core.maya_runtime_config import reload_runtime_config
from maya_core.storage import init_db
from maya_harness.harness_artifact_store import latest_artifacts
from maya_harness.harness_idempotency import init_action_ledger
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db, latest_events


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _new_state(workspace: Path, case_id: str, goal: str) -> tuple[HarnessGraphRunner, dict, str]:
    db_path = str(workspace / f"{case_id}.db")
    await init_db(db_path)
    await init_harness_db(db_path)
    await init_action_ledger(db_path)
    state = initial_harness_state(
        run_id=f"fast_{case_id}",
        thread_id=f"smoke:{case_id}",
        channel="imac",
        user_text=goal,
        workflow_type="document",
    )
    state["agentic_loop"] = True
    state["goal"] = goal
    state["last_user_instruction"] = goal
    return HarnessGraphRunner(db_path, planner_llm=lambda _prompt: "{}"), state, db_path


async def _execute(workspace: Path, case_id: str, goal: str, action: dict, **state_updates) -> tuple[dict, str]:
    runner, state, db_path = await _new_state(workspace, case_id, goal)
    state.update(state_updates)
    out = await runner._execute_agentic_action(state, action, approved=False)
    _require(out is not None, "agentic artifact action must be handled inline")
    return out, db_path


async def _test_allowed_file_create(workspace: Path) -> None:
    out, db_path = await _execute(
        workspace,
        "file",
        "Create a local file notes/fast-path-note.txt with a short note.",
        {"tool": "file.create", "args": {"path": "notes/fast-path-note.txt", "content": "fast path note"}},
    )
    created = Path(out["artifacts"][-1])
    _require(created.exists(), f"file not created: {created}")
    _require(created.read_text(encoding="utf-8") == "fast path note", "file content mismatch")
    events = await latest_events(db_path, out["run_id"], limit=20)
    _require(any(event["event"] == "permission_decision" and ": allow:" in event["details"] for event in events), "kernel allow not recorded")
    _require(any(event["event"] == "agentic_artifact_fast_path" for event in events), "fast-path event missing")
    _require(not any(event["event"] == "agentic_remap" for event in events), "fast path should not remap to slow document router")
    artifacts = await latest_artifacts(db_path, out["run_id"], limit=5)
    _require(artifacts and artifacts[0]["path"] == str(created), "structured artifact not recorded")


async def _test_allowed_docx_and_xlsx(workspace: Path) -> None:
    for tool, suffix, case_id in (("docx.create", ".docx", "docx"), ("xlsx.create", ".xlsx", "xlsx")):
        out, db_path = await _execute(
            workspace,
            case_id,
            f"Create a local {suffix} artifact about C0 executor reliability.",
            {"tool": tool, "args": {"topic": "C0 executor reliability", "content": "Local artifact creation should not time out."}},
        )
        created = Path(out["artifacts"][-1])
        _require(created.exists() and created.suffix == suffix, f"{tool} did not create {suffix}: {created}")
        events = await latest_events(db_path, out["run_id"], limit=20)
        _require(any(event["event"] == "permission_decision" and f"{tool}: allow:" in event["details"] for event in events), f"{tool} allow missing")
        _require(any(event["event"] == "agentic_artifact_fast_path" and tool in event["details"] for event in events), f"{tool} fast path missing")


async def _test_untrusted_body_with_maya_path_allows(workspace: Path) -> None:
    out, _db_path = await _execute(
        workspace,
        "research_body",
        "Create a Word document summarizing the browser research.",
        {"tool": "docx.create", "args": {"topic": "Browser research summary", "content": "Untrusted page text used as inert body content."}},
        untrusted_influence=True,
        last_observation={"source": "browser_page", "text_summary": "Untrusted page text used as inert body content."},
    )
    created = Path(out["artifacts"][-1])
    _require(created.exists() and created.suffix == ".docx", "untrusted body should not block Maya-derived local docx path")


async def _test_allowed_folder_and_project_create(workspace: Path) -> None:
    folder, folder_db = await _execute(
        workspace,
        "folder",
        "Create a folder called C0 Baseline Notes.",
        {"tool": "file.create", "args": {"path": "C0_Baseline_Notes", "kind": "folder"}},
    )
    folder_path = Path(folder["artifacts"][-1])
    _require(folder_path.exists() and folder_path.is_dir(), f"folder not created: {folder_path}")
    _require(folder_path.parent.resolve(strict=False) == (workspace / "notes").resolve(strict=False), f"folder should stay in notes workspace: {folder_path}")
    folder_events = await latest_events(folder_db, folder["run_id"], limit=20)
    _require(any(event["event"] == "permission_decision" and "file.create: allow:" in event["details"] for event in folder_events), "folder create allow missing")
    _require(any(event["event"] == "agentic_artifact_fast_path" for event in folder_events), "folder fast path missing")

    project, _project_db = await _execute(
        workspace,
        "project",
        "Create a project called C0 Capability Scratch.",
        {"tool": "file.create", "args": {"path": "C0_Capability_Scratch", "kind": "project"}},
    )
    project_path = Path(project["artifacts"][-1])
    _require(project_path.exists() and project_path.is_dir(), f"project folder not created: {project_path}")
    _require(project_path.parent.resolve(strict=False) == (workspace / "Projects").resolve(strict=False), f"project should stay in Projects workspace: {project_path}")


async def _test_owner_named_note_path_normalizes_to_markdown(workspace: Path) -> None:
    out, _db_path = await _execute(
        workspace,
        "local_note",
        "Create a local note about the C0 capability baseline.",
        {"tool": "file.create", "args": {"path": "C0 Capability Baseline", "content": "C0 capability baseline note with measured local artifact evidence."}},
    )
    created = Path(out["artifacts"][-1])
    _require(created.exists() and created.suffix == ".md", f"local note should normalize to markdown: {created}")
    _require(created.parent.resolve(strict=False) == (workspace / "notes").resolve(strict=False), f"local note should stay in notes workspace: {created}")


async def _test_forged_and_unsafe_paths_do_not_fast_path(workspace: Path) -> None:
    forged, forged_db = await _execute(
        workspace,
        "forged",
        "Create a local note.",
        {
            "tool": "file.create",
            "args": {
                "path": "notes/forged-source.txt",
                "path_source": "maya_derived",
                "content": "should not write",
            },
        },
    )
    _require(forged.get("pending_approval"), "forged path source should pause before fast path")
    _require(not (workspace / "notes" / "forged-source.txt").exists(), "forged path wrote a file")
    forged_events = await latest_events(forged_db, forged["run_id"], limit=20)
    _require(not any(event["event"] == "agentic_artifact_fast_path" for event in forged_events), "forged path entered fast path")

    outside, _outside_db = await _execute(
        workspace,
        "outside",
        "Create a local file /tmp/c0-fast-path-outside.txt with a note.",
        {"tool": "file.create", "args": {"path": "/tmp/c0-fast-path-outside.txt", "content": "outside"}},
    )
    _require(outside.get("pending_approval"), "outside workspace path should pause before fast path")

    existing_path = workspace / "notes" / "existing.txt"
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text("existing", encoding="utf-8")
    existing, _existing_db = await _execute(
        workspace,
        "existing",
        f"Create a local file {existing_path} with new text.",
        {"tool": "file.create", "args": {"path": str(existing_path), "content": "new"}},
    )
    _require(existing.get("pending_approval"), "existing target should pause before fast path")
    _require(existing_path.read_text(encoding="utf-8") == "existing", "existing target was overwritten")

    forged_folder, forged_folder_db = await _execute(
        workspace,
        "forged_folder",
        "Create a folder called C0 Baseline Notes.",
        {
            "tool": "file.create",
            "args": {
                "path": "Mallory Folder",
                "kind": "folder",
                "path_source": "maya_derived",
            },
        },
    )
    _require(forged_folder.get("pending_approval"), "forged folder name should pause before fast path")
    _require(not (workspace / "notes" / "mallory-folder").exists(), "forged folder was created")
    forged_folder_events = await latest_events(forged_folder_db, forged_folder["run_id"], limit=20)
    _require(not any(event["event"] == "agentic_artifact_fast_path" for event in forged_folder_events), "forged folder entered fast path")


async def _test_delivery_and_untrusted_sheet_do_not_fast_path(workspace: Path) -> None:
    delivery, _delivery_db = await _execute(
        workspace,
        "delivery",
        "Create a local file notes/delivery.txt with a note.",
        {
            "tool": "file.create",
            "args": {"path": "notes/delivery.txt", "content": "note", "recipient": "alice@example.com"},
        },
    )
    _require(delivery.get("pending_approval"), "delivery request should stay gated")
    _require(not (workspace / "notes" / "delivery.txt").exists(), "delivery-gated file should not be written")

    sheet, _sheet_db = await _execute(
        workspace,
        "sheet",
        "Create a spreadsheet.",
        {"tool": "xlsx.create", "args": {"sheet_name": "Mallory", "sheet_name_source": "owner_text"}},
        untrusted_influence=True,
    )
    _require(sheet.get("pending_approval"), "untrusted/forged sheet name should stay gated")


async def _run() -> None:
    previous = {key: os.environ.get(key) for key in ("MAYA_WORKSPACE_ROOT", "MAYA_TEST_MODE", "MAYA_AGENTIC_LOOP")}
    with tempfile.TemporaryDirectory(prefix="maya-agentic-fast-path-") as tmp:
        workspace = Path(tmp)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(workspace)
        os.environ["MAYA_TEST_MODE"] = "1"
        os.environ["MAYA_AGENTIC_LOOP"] = "1"
        reload_runtime_config()
        try:
            await _test_allowed_file_create(workspace)
            await _test_allowed_docx_and_xlsx(workspace)
            await _test_untrusted_body_with_maya_path_allows(workspace)
            await _test_allowed_folder_and_project_create(workspace)
            await _test_owner_named_note_path_normalizes_to_markdown(workspace)
            await _test_forged_and_unsafe_paths_do_not_fast_path(workspace)
            await _test_delivery_and_untrusted_sheet_do_not_fast_path(workspace)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            reload_runtime_config()


def main() -> None:
    asyncio.run(_run())
    print("agentic_artifact_fast_path_smoke: ok")


if __name__ == "__main__":
    main()
