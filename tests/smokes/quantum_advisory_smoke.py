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

from maya_core.quantum_advisory import quantum_context_hint
from maya_core.session_memory_store import init_session_memory_db, save_session_summary
from maya_core.storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-quantum-advisory-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_session_memory_db(db_path)
        await save_session_summary(
            db_path,
            "Shared session summary\n1) Main threads\na) context window\nb) telegram continuity",
        )

        os.environ.pop("ENABLE_QUANTUM_ADVISORY", None)
        enabled = await quantum_context_hint(db_path, "how should I think about context window continuity")
        _require("Quantum advisory signal:" in enabled, "advisory did not activate")
        _require("how to think" in enabled and "what to do next" in enabled, "advisory boundary missing")
        hard_fact = await quantum_context_hint(db_path, "what tasks are due by date")
        _require(hard_fact == "", "advisory leaked into hard facts")
        next_action = await quantum_context_hint(db_path, "what should I do next")
        _require(next_action == "", "advisory answered next action")

        os.environ["ENABLE_QUANTUM_ADVISORY"] = "0"
        disabled = await quantum_context_hint(db_path, "how should I think about context window")
        _require(disabled == "", "advisory disable flag failed")
        print("quantum_advisory_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
