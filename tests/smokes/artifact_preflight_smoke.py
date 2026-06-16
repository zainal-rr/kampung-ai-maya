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

from artifact_preflight import artifact_preflight_with_gemini, local_artifact_preflight


async def main() -> None:
    old_key = os.environ.pop("GOOGLE_API_KEY", None)
    try:
        with tempfile.TemporaryDirectory(prefix="maya-artifact-preflight-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            word = await artifact_preflight_with_gemini(db_path, "docx", "make router setup guide in Word")
            _require(word.source == "local", "missing-key preflight should fall back locally")
            _require(word.doc_kind == "generic_document", "missing-key Word preflight must not locally classify doc_kind")
            _require("admin password" in word.content.lower() or "scenario-specific" in word.content.lower(), "Word preflight too generic")

            excel = local_artifact_preflight("xlsx", "2-day Seoul food trip budget tracker")
            lowered_excel = excel.content.lower()
            _require("per-food" in lowered_excel or "per-restaurant" in lowered_excel, "Excel food preflight missing food rows")
            _require("variance" in lowered_excel and "totals" in lowered_excel, "Excel budget preflight missing formulas intent")

            deck = local_artifact_preflight("pptx", "2-day Seoul food trip presentation")
            lowered_deck = deck.content.lower()
            _require("narrative" in lowered_deck and "visual" in lowered_deck, "PowerPoint preflight missing narrative/visual guidance")
            _require(deck.lane_prefix == "local artifact preflight", "local lane prefix wrong")
    finally:
        if old_key:
            os.environ["GOOGLE_API_KEY"] = old_key
    print("artifact_preflight_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
