from __future__ import annotations

from maya_core.domain_knowledge_models import KnowledgeChunk


def build_domain_context(
    *,
    skill_name: str,
    matches: list[tuple[float, KnowledgeChunk]],
    budget_chars: int,
    answer_contract: str,
    max_chunk_chars: int,
    recipe_chunk_chars: int,
) -> str:
    parts: list[str] = [f"Domain knowledge ({skill_name}):"]
    used = len(parts[0])
    for _score, chunk in matches:
        chunk_cap = recipe_chunk_chars if chunk.whole_file else max_chunk_chars
        body = chunk.text[:chunk_cap].rstrip()
        block = f"[source: {chunk.source} § {chunk.header}]\n{body}"
        if used + len(block) > budget_chars:
            break
        parts.append(block)
        used += len(block)
    if len(parts) == 1:
        return ""
    parts.append(answer_contract)
    return "\n\n".join(parts)
