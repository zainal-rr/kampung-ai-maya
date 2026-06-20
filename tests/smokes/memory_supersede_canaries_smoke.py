"""W2-A supersede canaries (R1-R3).

Spec: docs/blast_radius_and_retrieval_design_2026-06-12.md.
Asserts supersede-not-overwrite keeps history, that superseded != forgotten,
and that forget removes the WHOLE chain (no resurrect via history).
"""

from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from maya_memory.canonical_memory import (  # noqa: E402
    forget_canonical_memory,
    search_canonical_direct_fact,
    upsert_canonical_memory,
)
from maya_memory.canonical_memory_supersede import canonical_memory_history  # noqa: E402
from maya_memory.memory_canaries import check_memory_canaries, seed_memory_canaries  # noqa: E402


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


async def _save(db: str, content: str) -> None:
    await upsert_canonical_memory(
        db,
        raw_text=content,
        content=content,
        kind="fact",
        scope="global",
        source_channel="test",
        confidence="high",
    )


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-supersede-") as tmp:
        db = str(Path(tmp) / "m.db")

        # R1 — supersede keeps history: current returns new, history has both.
        await _save(db, "my rent is 1500")
        await _save(db, "my rent is 1800")
        current = await search_canonical_direct_fact(db, "what is my rent")
        _require(current == ["my rent is 1800"], f"R1 FAILED: current recall wrong ({current})")
        history = await canonical_memory_history(db, "rent")
        contents = [h["content"] for h in history]
        statuses = {h["status"] for h in history}
        _require("my rent is 1800" in contents and "my rent is 1500" in contents,
                 f"R1 FAILED: history missing a value ({history})")
        _require(statuses == {"active", "superseded"}, f"R1 FAILED: status set wrong ({statuses})")

        # Re-saving the SAME value must NOT grow history (reinforce in place).
        await _save(db, "my rent is 1800")
        _require(len(await canonical_memory_history(db, "rent")) == 2,
                 "R1 FAILED: re-save of identical value grew history")

        # R2 — superseded is retrievable as history; a forgotten fact is not.
        pre = await canonical_memory_history(db, "rent")
        _require(any(h["status"] == "superseded" for h in pre),
                 "R2 FAILED: superseded value not retrievable as history")

        # R3 — forget removes the WHOLE chain (no resurrect via history).
        forgotten = await forget_canonical_memory(db, "rent")
        _require(forgotten >= 2, f"R3 FAILED: forget did not cover the chain ({forgotten})")
        _require(await search_canonical_direct_fact(db, "what is my rent") is None,
                 "R3 FAILED: direct recall leaked after forget")
        _require(await canonical_memory_history(db, "rent") == [],
                 "R3 FAILED: history leaked a forgotten fact")

        # R4 — explicit user re-save after forget reactivates the stable base row
        # without resurrecting the old history chain.
        await _save(db, "my rent is 2000")
        current_after_resave = await search_canonical_direct_fact(db, "what is my rent")
        _require(current_after_resave == ["my rent is 2000"],
                 f"R4 FAILED: explicit re-save did not reactivate current value ({current_after_resave})")
        history_after_resave = await canonical_memory_history(db, "rent")
        _require(len(history_after_resave) == 1
                 and history_after_resave[0]["content"] == "my rent is 2000"
                 and history_after_resave[0]["status"] == "active",
                 f"R4 FAILED: forgotten history leaked after explicit re-save ({history_after_resave})")

        # R5 — repeated canary seeding in one DB must not collide with the
        # deterministic memory_id of a forgotten/expired base row.
        canary_db = str(Path(tmp) / "canaries.db")
        await seed_memory_canaries(canary_db)
        await seed_memory_canaries(canary_db)
        active = await search_canonical_direct_fact(canary_db, "what is my memory canary active color")
        _require(active == ["my memory canary active color is azure"],
                 f"R5 FAILED: active canary recall wrong after reseed ({active})")
        baseline = await check_memory_canaries(canary_db)
        _require(baseline["passed"], f"R5 FAILED: canary reseed baseline failed ({baseline['failures']})")

    print("memory supersede canaries R1-R5: PASS")


if __name__ == "__main__":
    asyncio.run(main())
