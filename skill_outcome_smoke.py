from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from skill_memory_store import list_skill_memory
from skill_outcome_store import recent_skill_outcomes, record_skill_outcome
from skill_store import init_skill_db, list_skill_proposals, upsert_skill


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-skill-outcome-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_skill_db(db_path)
        await upsert_skill(db_path, "flight_search", "Flight Search", "Find flights.", "bounded", "policy", "active", "test")
        await record_skill_outcome(
            db_path,
            skill_id="flight_search",
            user_request="find flights to Penang",
            outcome="success",
            channel="telegram",
            selected_lane="Gemini",
        )
        await record_skill_outcome(db_path, skill_id="flight_search", user_request="find cheap flights to Penang", outcome="success")
        memory = await list_skill_memory(db_path, "flight_search")
        _require(any(item["kind"] == "example" for item in memory), "repeated success did not add example memory")
        await record_skill_outcome(db_path, skill_id="flight_search", user_request="book flight", outcome="failure", missing_step="booking unavailable")
        await record_skill_outcome(db_path, skill_id="flight_search", user_request="book cheaper flight", outcome="failure", missing_step="booking unavailable")
        proposals = await list_skill_proposals(db_path)
        _require(any("repeated failures" in item["summary"] for item in proposals), "repeated failure did not propose improvement")
        await record_skill_outcome(db_path, skill_id="flight_search", user_request="wrong airport", outcome="user_corrected", user_correction="Use KUL")
        outcomes = await recent_skill_outcomes(db_path)
        _require(any(item["outcome"] == "user_corrected" for item in outcomes), "correction outcome missing")
        _require(any(item["channel"] == "telegram" and item["selected_lane"] == "Gemini" for item in outcomes), "channel or lane missing")
    print("skill_outcome_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
