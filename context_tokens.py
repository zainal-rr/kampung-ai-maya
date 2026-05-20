from __future__ import annotations


def estimate_tokens(text: str) -> int:
    clean = " ".join(str(text or "").split())
    if not clean:
        return 0
    word_estimate = len(clean.split()) * 1.35
    char_estimate = len(clean) / 4
    return max(1, int(max(word_estimate, char_estimate)))


def estimate_row_tokens(rows: list[dict[str, str]]) -> int:
    return sum(estimate_tokens(f"{row.get('role', '')}: {row.get('content', '')}") for row in rows)


def split_older_rows_by_token_budget(
    rows: list[dict[str, str]],
    keep_recent_tokens: int,
    keep_recent_min: int,
) -> list[dict[str, str]]:
    recent_budget = 0
    split_index = len(rows)
    recent_count = 0
    for index in range(len(rows) - 1, -1, -1):
        row_tokens = estimate_tokens(rows[index].get("content", ""))
        should_keep_for_count = recent_count < keep_recent_min
        should_keep_for_budget = recent_budget + row_tokens <= keep_recent_tokens
        if not should_keep_for_count and not should_keep_for_budget:
            break
        recent_budget += row_tokens
        recent_count += 1
        split_index = index
    return rows[:split_index]
