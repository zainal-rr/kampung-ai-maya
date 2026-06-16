from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import tempfile
from pathlib import Path

from maya_memory.canonical_memory import search_relevant_canonical_memories
from maya_core.omi_context_sieve import ingest_omi_decision, sieve_omi_transcript
from sieve import SieveNode
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-omi-sieve-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)

        noise = await sieve_omi_transcript("[silence] can you hear me")
        _require(not noise.accepted and noise.status == "noise", "noise was accepted")

        sensitive = await sieve_omi_transcript("Maya remember that my API key is sk-test-1234567890")
        _require(not sensitive.accepted, "sensitive transcript was accepted")

        async def fake_provider(_prompt: str) -> str:
            return json.dumps({
                "status": "accepted",
                "summary": "Zainal decided the router setup guide needs a PuTTY command example.",
                "confidence": "medium",
            })

        decision = await sieve_omi_transcript(
            "Zainal decided the router setup guide needs a PuTTY command example.",
            fake_provider,
        )
        _require(decision.accepted, "provider decision was rejected")
        memory_id = await ingest_omi_decision(db_path, decision, source_ref="omi:test")
        _require(bool(memory_id), "accepted Omi memory was not stored")
        recalled = await search_relevant_canonical_memories(db_path, "router setup putty", limit=3)
        _require(any("PuTTY command example" in item for item in recalled), "stored Omi context not retrievable")

        watch_dir = Path(tmp) / "watch"
        watch_dir.mkdir()
        transcript = watch_dir / "omi.json"
        transcript.write_text(
            json.dumps({"text": "Zainal decided the Seoul deck should use dark visual slides."}),
            encoding="utf-8",
        )
        node = SieveNode(str(watch_dir), db_path)
        node._distill_with_gemini = fake_provider
        await node.process_file("omi.json")
        _require(not transcript.exists(), "processed Omi transcript was not removed")
    print("omi_context_sieve_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
