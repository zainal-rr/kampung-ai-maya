from __future__ import annotations

import asyncio
import tempfile

from skill_outcome_store import record_skill_outcome
from skill_performance_analyzer import analyze_skill_performance, skill_performance_text
from skill_store import init_skill_db, list_skill_proposals, upsert_skill


async def main() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        await init_skill_db(tmp.name)
        await upsert_skill(tmp.name, "stale_skill", "Stale", "Unused", "safe", "none", "active", "test")
        for _ in range(2):
            await record_skill_outcome(
                tmp.name,
                skill_id="flight_research",
                user_request="find flight",
                outcome="failure",
                missing_step="date compare",
            )
            await record_skill_outcome(tmp.name, skill_id="slide_review", user_request="check slide", outcome="success")
        await record_skill_outcome(tmp.name, skill_id="slide_review", user_request="wrong tone", outcome="user_corrected", user_correction="Use softer tone")
        result = await analyze_skill_performance(tmp.name)
        assert result["failure"] == ["flight_research:2"]
        assert result["success"] == ["slide_review:2"]
        assert result["corrections"] == ["slide_review:1"]
        proposals = await list_skill_proposals(tmp.name, limit=20)
        summaries = " ".join(item["summary"] for item in proposals)
        assert "failed" in summaries
        assert "succeeded" in summaries
        assert "correction" in summaries
        assert "no recent outcome" in summaries
        text = await skill_performance_text(tmp.name)
        assert "failure" in text
    print("skill_performance_analyzer_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
