from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from openpyxl import Workbook

from artifact_builder import ArtifactBuilder
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


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artifact-gate-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            router = DocumentActionRouter(db_path, workspace=Path(tmp) / "Maya")
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
            draft_reply = await EverydayCommandRouter(db_path).handle("give me the rough", "telegram")
            _require(draft_reply is not None and "[file:" in draft_reply, f"rough draft should attach: {draft_reply}")
            _require("bad.xlsx" in draft_reply, f"rough draft should reference failed draft: {draft_reply}")

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
            _require(await get_preference(db_path, "maya_last_document_path") in {None, ""}, "failed artifact should not become latest document")
            print("artifact_delivery_gate_smoke: ok")
        finally:
            _restore_env("ANTHROPIC_API_KEY", old_anthropic)


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
