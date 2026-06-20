from __future__ import annotations

from maya_core.config import get_env
from maya_memory.canonical_memory_embeddings import (
    COSINE_WEIGHT,
    EmbedCall,
    default_direct_embedding_agent,
    default_embedding_model_name,
    score_candidates_with_embeddings,
)

# W2-B eval selected this threshold on the 2026-06-17 case set. It is
# deliberately env-overridable because the value is fitted to a small eval, not
# a universal optimum.
DIRECT_SEMANTIC_WEAK_THRESHOLD = 30
DIRECT_SEMANTIC_MIN_COSINE = 0.76
DIRECT_SEMANTIC_MIN_MARGIN = 0.05


def direct_semantic_weak_threshold() -> int:
    value = get_env("MEMORY_DIRECT_SEMANTIC_WEAK_THRESHOLD", str(DIRECT_SEMANTIC_WEAK_THRESHOLD))
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return DIRECT_SEMANTIC_WEAK_THRESHOLD


def direct_semantic_min_cosine() -> float:
    value = get_env("MEMORY_DIRECT_SEMANTIC_MIN_COSINE", str(DIRECT_SEMANTIC_MIN_COSINE))
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return DIRECT_SEMANTIC_MIN_COSINE


def direct_semantic_min_margin() -> float:
    value = get_env("MEMORY_DIRECT_SEMANTIC_MIN_MARGIN", str(DIRECT_SEMANTIC_MIN_MARGIN))
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return DIRECT_SEMANTIC_MIN_MARGIN


async def semantic_direct_recall_candidates(
    db_path: str,
    query: str,
    candidates: list[tuple[int, str, str]],
    *,
    embedding_agent: EmbedCall | None = None,
    weak_threshold: int | None = None,
    min_cosine: float | None = None,
    min_margin: float | None = None,
) -> list[tuple[int, str, str]]:
    """Surface direct-recall candidates only when lexical evidence is weak.

    `candidates` must already be active/current canonical rows. This function
    scores that pool; it does not search the database or resurrect memory.
    """
    if not candidates:
        return []
    threshold = direct_semantic_weak_threshold() if weak_threshold is None else weak_threshold
    if candidates[0][0] > threshold:
        return []
    agent = embedding_agent if embedding_agent is not None else default_direct_embedding_agent()
    if agent is None:
        return []
    floor = direct_semantic_min_cosine() if min_cosine is None else min_cosine
    margin = direct_semantic_min_margin() if min_margin is None else min_margin
    semantic = await score_candidates_with_embeddings(
        db_path,
        query,
        candidates,
        agent,
        model=default_embedding_model_name(),
    )
    if not semantic:
        return []
    top = semantic[0]
    runner_up = semantic[1] if len(semantic) > 1 else None
    if top[0] < floor:
        return []
    if runner_up is not None and (top[0] - runner_up[0]) < margin:
        return []
    cosine, lexical_score, memory_id, content = top
    return [(lexical_score + int(cosine * COSINE_WEIGHT), memory_id, content)]
