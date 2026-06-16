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

from maya_core.context_layers import init_context_layers_db
from maya_harness.harness_artifact_store import init_harness_artifact_db
from maya_harness.harness_store import init_harness_db
from maya_core.lesson_store import init_lesson_db
from maya_core.routine_store import init_routine_db
from maya_core.session_memory_store import init_session_memory_db
from maya_core.skill_store import init_skill_db
from maya_core.storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-semantic-artifact-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)

        old_test_mode = os.environ.get("MAYA_TEST_MODE")
        old_allow = os.environ.get("MAYA_TEST_ALLOW_SEMANTIC_PROVIDER")
        old_xai = os.environ.get("XAI_API_KEY")

        import maya_documents.artifact_semantic_resolver as resolver

        old_news = resolver.TheNews
        try:
            os.environ["MAYA_TEST_MODE"] = "1"
            os.environ.pop("MAYA_TEST_ALLOW_SEMANTIC_PROVIDER", None)
            os.environ["XAI_API_KEY"] = "test-key"

            skipped = await resolver.resolve_semantic_artifact_intent(db_path, "A Tokyo food cost sheet.")
            _require(skipped is None, "semantic provider should be disabled in normal test mode")

            ambiguous = await resolver.resolve_semantic_artifact_intent(db_path, "make me a Seoul food trip document")
            _require(ambiguous is not None and ambiguous.action == "clarify", "generic document should clarify")
            _require("Word doc, Excel sheet, or PowerPoint slides" in ambiguous.question, ambiguous.question)

            os.environ["MAYA_TEST_ALLOW_SEMANTIC_PROVIDER"] = "1"
            resolver.TheNews = _FakeNews

            xlsx = await resolver.resolve_semantic_artifact_intent(db_path, "A Tokyo food cost sheet.")
            _require(xlsx is not None, "semantic resolver should classify artifact phrase")
            _require(xlsx.action == "create", f"expected create, got {xlsx}")
            _require(xlsx.kind == "xlsx", f"expected xlsx, got {xlsx}")
            _require("Tokyo" in xlsx.topic and "food" in xlsx.topic.lower(), f"bad topic: {xlsx.topic!r}")
            _require(xlsx.domain == "travel_food_budget", f"bad food budget domain: {xlsx.domain!r}")
            _require(xlsx.cost_recorded, "semantic provider use should record cost")

            collapsed = await resolver.resolve_semantic_artifact_intent(
                db_path, "Give me a Tokyo Excel sheet for 2 days with 2 people."
            )
            _require(collapsed is not None and collapsed.action == "create", f"expected create, got {collapsed}")
            _require(collapsed.kind == "xlsx", f"expected xlsx, got {collapsed}")
            _require(collapsed.domain == "travel_budget", f"bad travel budget domain: {collapsed.domain!r}")
            _require("travel budget" in collapsed.topic.lower(), f"collapsed topic was not enriched: {collapsed.topic!r}")
            _require(collapsed.parameters.get("days") == 2, f"days not preserved: {collapsed.parameters!r}")
            _require(collapsed.parameters.get("people_count") == 2, f"people not preserved: {collapsed.parameters!r}")

            soft_wording = await resolver.resolve_semantic_artifact_intent(
                db_path, "I need something to track Tokyo food costs for two days and two people"
            )
            _require(
                soft_wording is not None and soft_wording.action == "create",
                f"soft artifact wording should reach semantic provider: {soft_wording}",
            )
            _require(soft_wording.kind == "xlsx", f"expected soft wording xlsx, got {soft_wording}")

            edit = await resolver.resolve_semantic_artifact_intent(
                db_path, "change the number of people in the worksheet to two"
            )
            _require(edit is not None and edit.action == "edit", f"expected edit, got {edit}")
            _require("two" in edit.instruction.lower(), f"edit instruction lost content: {edit.instruction!r}")

            pronoun_edit = await resolver.resolve_semantic_artifact_intent(db_path, "change it to two person now")
            _require(
                pronoun_edit is not None and pronoun_edit.action == "edit",
                f"expected pronoun edit, got {pronoun_edit}",
            )

            destination_edit = await resolver.resolve_semantic_artifact_intent(db_path, "move it from Seoul to Kyoto")
            _require(
                destination_edit is not None and destination_edit.action == "edit",
                f"expected destination edit, got {destination_edit}",
            )

            none = await resolver.resolve_semantic_artifact_intent(db_path, "why is quantum computing hard")
            _require(none is None, f"normal chat should not become artifact intent: {none}")

            trip_chat = await resolver.resolve_semantic_artifact_intent(db_path, "Can you make me a two days trip to Kyoto?")
            _require(trip_chat is None, f"plain trip planning should stay chat, not artifact: {trip_chat}")

            print("artifact_semantic_resolver_smoke: ok")
        finally:
            resolver.TheNews = old_news
            _restore_env("MAYA_TEST_MODE", old_test_mode)
            _restore_env("MAYA_TEST_ALLOW_SEMANTIC_PROVIDER", old_allow)
            _restore_env("XAI_API_KEY", old_xai)


class _FakeNews:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def chat(self, messages):
        text = messages[-1]["content"].lower()
        if "food cost sheet" in text:
            return (
                '{"action":"create","kind":"xlsx","topic":"Tokyo",'
                '"instruction":"Tokyo food cost tracker","question":"","save_copy":false}'
            )
        if "excel sheet" in text:
            return (
                '{"action":"create","kind":"xlsx","topic":"Tokyo",'
                '"instruction":"Tokyo Excel sheet","question":"","save_copy":false}'
            )
        if "track tokyo food costs" in text:
            return (
                '{"action":"create","kind":"xlsx","topic":"Tokyo food costs",'
                '"instruction":"track Tokyo food costs for two days and two people",'
                '"parameters":{"days":2,"people_count":2},"question":"","save_copy":false}'
            )
        if "number of people" in text or "two person" in text:
            return (
                '{"action":"edit","kind":"xlsx","topic":"","instruction":'
                '"change the number of people in the latest workbook to two","question":"","save_copy":false}'
            )
        if "from seoul to kyoto" in text:
            return (
                '{"action":"edit","kind":"","topic":"","instruction":'
                '"move the latest artifact from Seoul to Kyoto","question":"","save_copy":false}'
            )
        if "two days trip to kyoto" in text:
            return (
                '{"action":"create","kind":"md","topic":"Kyoto trip",'
                '"instruction":"make a two days trip to Kyoto","question":"","save_copy":false}'
            )
        return '{"action":"none","kind":"","topic":"","instruction":"","question":"","save_copy":false}'


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
