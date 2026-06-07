from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from openpyxl import Workbook

from artifact_builder import ArtifactBuilder
from artifact_quality import ArtifactQualityResult
from context_layers import init_context_layers_db
from document_actions import DocumentActionRouter
from harness_artifact_store import init_harness_artifact_db
from harness_store import init_harness_db
from lesson_store import init_lesson_db
from markdown_drafter import MarkdownDraft
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db
from travel_budget import TravelParty
from travel_budget_workbook import _build_workbook


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artifact-retry-") as tmp:
        old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
        old_attempts = os.environ.get("ARTIFACT_QA_MAX_ATTEMPTS")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ["ARTIFACT_QA_MAX_ATTEMPTS"] = "4"
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        try:
            await _word_retries_until_pass(db_path, Path(tmp) / "Maya")
            await _builder_retries_until_pass(db_path, Path(tmp) / "bad.xlsx")
            print("artifact_retry_loop_smoke: ok")
        finally:
            _restore_env("ANTHROPIC_API_KEY", old_anthropic)
            _restore_env("ARTIFACT_QA_MAX_ATTEMPTS", old_attempts)


async def _word_retries_until_pass(db_path: str, workspace: Path) -> None:
    import document_actions as da

    old_draft = da.draft_markdown_with_gemini
    old_preflight = da.artifact_preflight_with_gemini
    router = DocumentActionRouter(db_path, workspace=workspace)
    quality_calls = 0
    repairs: list[int] = []

    async def fake_quality(path: Path, topic: str) -> ArtifactQualityResult:
        nonlocal quality_calls
        quality_calls += 1
        if quality_calls < 3:
            return ArtifactQualityResult("docx", str(path), False, issues=[f"forced failure {quality_calls}"])
        return ArtifactQualityResult("docx", str(path), True, summary="forced pass")

    async def fake_repair(path: Path, topic: str, quality: ArtifactQualityResult, attempt: int = 2) -> bool:
        repairs.append(attempt)
        return True

    try:
        da.draft_markdown_with_gemini = _fake_draft
        da.artifact_preflight_with_gemini = _fake_preflight
        router._word_quality = fake_quality
        router._repair_word_doc = fake_repair
        reply = await router._create_word("Tokyo food trip", False, "telegram")
    finally:
        da.draft_markdown_with_gemini = old_draft
        da.artifact_preflight_with_gemini = old_preflight

    _require("[file:" in reply, f"passed retry did not attach: {reply}")
    _require(repairs == [2, 3], f"Word repair loop did not retry correctly: {repairs}")


async def _builder_retries_until_pass(db_path: str, path: Path) -> None:
    workbook = Workbook()
    workbook.active.title = "Sheet"
    workbook.active["A1"] = "not enough"
    workbook.save(path)
    rebuilds: list[int] = []

    def rebuild(attempt: int, quality: ArtifactQualityResult) -> None:
        rebuilds.append(attempt)
        _build_workbook(
            path,
            {"destination": "Tokyo", "origin": "Kuala Lumpur", "people_count": 2, "people_source": "test", "days": 2, "food_focus": True},
            TravelParty(2, "test"),
        )

    result = await ArtifactBuilder(db_path).finish_xlsx(
        path,
        "Tokyo food budget tracker",
        "telegram",
        run_id="retry_loop_smoke",
        source_tool="smoke",
        label="an editable Tokyo food budget tracker",
        rebuild=rebuild,
    )
    _require(result.quality.passed, f"builder did not pass after rebuild: {result.quality.issues}")
    _require("[file:" in result.reply, f"passed builder retry did not attach: {result.reply}")
    _require(rebuilds == [2], f"builder did not rebuild once: {rebuilds}")


async def _fake_draft(db_path: str, topic: str, preflight_context: str = "") -> MarkdownDraft:
    return MarkdownDraft("# Tokyo Food Trip\n\n## Overview\n\nA useful Tokyo food trip plan.", grounded=False)


async def _fake_preflight(db_path: str, artifact_type: str, topic: str):
    from artifact_preflight import ArtifactPreflight

    return ArtifactPreflight(artifact_type, topic, "gemini", "runtime preflight", True)


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
