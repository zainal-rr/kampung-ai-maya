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
    with tempfile.TemporaryDirectory(prefix="maya-quantum-leaf-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_session_memory_db(db_path)
        await save_session_summary(
            db_path,
            "Shared session summary\n1) Main threads\na) memory architecture\nb) PowerPoint design taste\nc) self-heal workflow",
        )
        os.environ["ENABLE_QUANTUM_ADVISORY"] = "1"
        advisory = await quantum_context_hint(db_path, "how should I think about memory and design continuity")
        _require("Quantum advisory signal:" in advisory, "advisory route did not activate")
        blocked_inputs = (
            "/complex self heal Maya",
            "make me a PowerPoint about Seoul",
            "what should I do next",
            "delete old project files",
            "what is the API key",
            "how should I think about budget cost",
        )
        for text in blocked_inputs:
            result = await quantum_context_hint(db_path, text)
            _require(result == "", f"quantum advisory leaked into mixed route: {text}")
    print("quantum_leaf_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
