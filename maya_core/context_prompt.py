from __future__ import annotations


def format_context_blocks(
    facts: list[dict[str, str | float]],
    vibes: list[dict[str, str | float]],
    summaries: list[dict[str, str | int]],
) -> list[str]:
    blocks = []
    fact_lines = [str(item["text"]).strip() for item in facts if str(item["text"]).strip()]
    if fact_lines:
        blocks.append("Hard facts and rules:\n" + "\n".join(_lettered(fact_lines[:6])))
    vibe_lines = [str(item["text"]).strip() for item in vibes if str(item["text"]).strip()]
    if vibe_lines:
        blocks.append("Vibes and themes:\n" + "\n".join(_lettered(vibe_lines[:4])))
    summary_lines = [str(item["summary"]).strip() for item in summaries if str(item["summary"]).strip()]
    if summary_lines:
        blocks.append("Shared compacted context:\n" + "\n\n".join(summary_lines[:2]))
    return blocks


def _lettered(lines: list[str]) -> list[str]:
    return [f"{chr(97 + idx)}) {line}" for idx, line in enumerate(lines)]
