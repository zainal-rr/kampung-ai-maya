from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
import types
from pathlib import Path

from maya_core.assistant import KampungAssistant
from maya_core.lesson_store import init_lesson_db
from maya_core.routine_store import init_routine_db
from maya_core.route_tracker import last_route_text
from maya_core.source_aware_research import (
    format_source_research,
    should_use_source_research,
    source_aware_research,
)
from maya_core.skill_store import init_skill_db
from maya_core.storage import init_db


async def main() -> None:
    assert should_use_source_research("Research this with sources: Python packaging")
    assert should_use_source_research("Research about Python packaging with citations")
    assert not should_use_source_research("make me a Seoul food trip doc")
    await _module_fake_provider_check()
    await _router_check()
    print("source_aware_research_smoke: ok")


async def _module_fake_provider_check() -> None:
    async def provider(prompt: str):
        assert "Question:" in prompt
        return "Use official packaging docs first.", [("Python Packaging", "https://packaging.python.org/")]

    result = await source_aware_research(":memory:", "Research this with sources: Python packaging", provider=provider)
    assert result.grounded
    assert result.confidence == "high"
    text = format_source_research(result, channel="telegram")
    assert "Sources:" in text and "https://packaging.python.org/" in text

    blocked = await source_aware_research(":memory:", "Research this API key sk-12345678901234567890")
    assert "can't expose sensitive" in blocked.answer.lower()


async def _router_check() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await init_routine_db(db_path)
        await init_skill_db(db_path)
        assistant = KampungAssistant(db_path=db_path)

        async def fake_source(self, text, memory_context, skill_context, channel="telegram"):
            return "Grounded answer\n\nSources:\n1) Source: https://example.com/source"

        assistant.model_lanes.source_research_response = types.MethodType(fake_source, assistant.model_lanes)
        reply = await assistant.handle_text("Research this with sources: router setup", channel="telegram")
        assert "https://example.com/source" in reply
        route = await last_route_text(db_path)
        assert "Gemini source-aware research" in route


if __name__ == "__main__":
    asyncio.run(main())
