"""Domain knowledge retrieval: deterministic lexical RAG over skill KBs.

A domain skill is any markdown file in ``maya_skills/active/`` that declares a
``## Knowledge Base`` section pointing at a docs tree (for example
``docs/networking/``). The skill file itself is the routing configuration:

- ``## Trigger Phrases`` bullets define activation. Quoted phrases,
  parenthesized term lists, and ALL-CAPS acronyms are *strong* triggers that
  activate alone; remaining content words are *weak* triggers that need two
  distinct word-boundary matches. ``non-trigger`` bullets veto activation when
  no strong trigger fired.
- The numbered list in ``## Knowledge Base`` defines retrieval-order
  preference between KB subdirectories (recipes vs architecture vs protocols).

Retrieval is lexical and replay-safe: KB files are chunked at ``##`` headers,
chunks are scored by token overlap (same tokenizer as canonical memory) with
a directory boost from the retrieval order, and only chunks above a minimum
overlap are injected, under a hard character budget. When nothing clears the
bar, nothing is injected: silence over wrong-domain noise.

Proposed skills are inert: only ``maya_skills/active`` is scanned by default.
"""

from __future__ import annotations

from pathlib import Path

from maya_memory.canonical_memory_text import memory_tokens
from maya_core.domain_knowledge_chunks import directory_boosts, kb_chunks
from maya_core.domain_knowledge_context_builder import build_domain_context
from maya_core.domain_knowledge_models import DomainSkill, KnowledgeChunk
from maya_core.domain_knowledge_parse import parse_domain_skill, word_match
from maya_core.repo_paths import repo_root

REPO_ROOT = repo_root(__file__)
DEFAULT_SKILL_DIR = REPO_ROOT / "maya_skills" / "active"

MAX_CONTEXT_CHARS = 6000
MAX_CHUNK_CHARS = 2600
RECIPE_CHUNK_CHARS = 5000
MAX_CHUNKS = 3
MIN_CHUNK_OVERLAP = 2
MIN_WEAK_HITS = 2

_skills_cache: dict[str, tuple[tuple[tuple[str, float], ...], list["DomainSkill"]]] = {}
_chunk_cache: dict[str, tuple[float, list["KnowledgeChunk"]]] = {}


def load_domain_skills(skill_dir: Path | str | None = None) -> list[DomainSkill]:
    directory = Path(skill_dir) if skill_dir else DEFAULT_SKILL_DIR
    if not directory.is_dir():
        return []
    stamps = tuple(sorted((p.name, p.stat().st_mtime) for p in directory.glob("*.md")))
    cached = _skills_cache.get(str(directory))
    if cached and cached[0] == stamps:
        return cached[1]
    skills = []
    for path in sorted(directory.glob("*.md")):
        skill = parse_domain_skill(path, REPO_ROOT)
        if skill:
            skills.append(skill)
    _skills_cache[str(directory)] = (stamps, skills)
    return skills


def detect_domain_skill(query: str, skills: list[DomainSkill]) -> DomainSkill | None:
    lowered = " ".join(str(query).lower().split())
    tokens = memory_tokens(lowered)
    best: tuple[int, DomainSkill] | None = None
    for skill in skills:
        strong_hits = [t for t in skill.strong_triggers if word_match(t, lowered)]
        weak_hits = tokens & skill.weak_triggers
        vetoed = any(phrase in lowered for phrase in skill.non_triggers)
        if vetoed and not strong_hits:
            continue
        if strong_hits or len(weak_hits) >= MIN_WEAK_HITS:
            score = 2 * len(strong_hits) + len(weak_hits)
            if best is None or score > best[0]:
                best = (score, skill)
    return best[1] if best else None


def retrieve_domain_chunks(query: str, skill: DomainSkill, limit: int = MAX_CHUNKS) -> list[tuple[float, KnowledgeChunk]]:
    tokens = memory_tokens(query)
    if not tokens:
        return []
    boosts = directory_boosts(query, skill.retrieval_order)
    scored: list[tuple[float, int, KnowledgeChunk]] = []
    for index, chunk in enumerate(kb_chunks(skill, REPO_ROOT, _chunk_cache)):
        overlap = tokens & chunk.tokens
        if len(overlap) < MIN_CHUNK_OVERLAP:
            continue
        header_bonus = 2 * len(tokens & memory_tokens(f"{chunk.source} {chunk.header}"))
        boost = next((b for prefix, b in boosts if chunk.source.startswith(prefix)), 1.0)
        scored.append(((len(overlap) + header_bonus) * boost, index, chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [(score, chunk) for score, _idx, chunk in scored[:limit]]


def domain_knowledge_context(
    query: str,
    *,
    skill_dir: Path | str | None = None,
    budget_chars: int = MAX_CONTEXT_CHARS,
) -> tuple[str, DomainSkill | None]:
    """Return (context_block, matched_skill). Empty context when nothing clears the bar."""
    skills = load_domain_skills(skill_dir)
    if not skills:
        return "", None
    skill = detect_domain_skill(query, skills)
    if not skill:
        return "", None
    matches = retrieve_domain_chunks(query, skill)
    if not matches:
        return "", None
    context = build_domain_context(
        skill_name=skill.name,
        matches=matches,
        budget_chars=budget_chars,
        answer_contract=_ANSWER_CONTRACT,
        max_chunk_chars=MAX_CHUNK_CHARS,
        recipe_chunk_chars=RECIPE_CHUNK_CHARS,
    )
    if not context:
        return "", None
    return context, skill


# Phase 5 finding 2026-06-12: answers cited recipes but dropped their mandatory
# sections (VRF without rollback, DCF without a computed range, cloud design
# without the provider mapping/pricing caveat). The contract makes recipe
# completeness explicit instead of implied.
_ANSWER_CONTRACT = (
    "Domain answer contract:\n"
    "1. Ground the answer in these sources and NAME the source recipe or doc used.\n"
    "2. Follow the retrieved recipe completely. If it contains verification steps, "
    "rollback, a worked sensitivity range, provider mappings (AWS/GCP/Azure), pricing "
    "or advice caveats, or limitations, the answer MUST include each of them. "
    "Dropping a mandatory recipe section is a wrong answer.\n"
    "For cloud architecture recipes, if the source contains an AWS/GCP/Azure service "
    "mapping, include a compact mapping table or mapping lines even when the user "
    "asks primarily about one cloud provider.\n"
    "3. Numbers are computed with shown formulas. When the recipe requires a range, "
    "compute and state the range values; do not give a single point value and do not "
    "defer sensitivity to a later step.\n"
    "4. If these sources do not cover the question, say the answer is unverified general knowledge."
)


def strong_domain_skill_id(
    query: str,
    *,
    skill_dir: Path | str | None = None,
) -> str:
    """Return the skill_id whose STRONG trigger matches the query (veto-aware), else "".

    Used by the artifact router for precedence (Phase 5 finding 2026-06-12:
    'design the network for a new branch campus' was hijacked into a
    Word/Excel/PPT clarification). Weak-only matches deliberately do not count:
    only an explicit strong trigger may divert a message away from the
    artifact path.
    """
    lowered = " ".join(str(query).lower().split())
    if not lowered:
        return ""
    for skill in load_domain_skills(skill_dir):
        strong_hit = any(word_match(t, lowered) for t in skill.strong_triggers)
        vetoed = any(phrase in lowered for phrase in skill.non_triggers)
        if strong_hit and not vetoed:
            return skill.skill_id
    return ""


def domain_knowledge_context_for_skill(
    query: str,
    skill_id: str,
    *,
    skill_dir: Path | str | None = None,
    budget_chars: int = MAX_CONTEXT_CHARS,
) -> str:
    """Retrieve against a KNOWN skill, skipping trigger detection.

    Sticky follow-up path (Phase 5 finding 2026-06-12: 'now assess the
    preference share issuance from an investor's perspective' lost the finance
    domain because follow-up wording missed every trigger). Fail-silent: if the
    query's tokens do not overlap the pack's chunks, returns "" — an unrelated
    follow-up injects nothing.
    """
    skill = next((s for s in load_domain_skills(skill_dir) if s.skill_id == skill_id), None)
    if skill is None:
        return ""
    matches = retrieve_domain_chunks(query, skill)
    if not matches:
        return ""
    return build_domain_context(
        skill_name=skill.name,
        matches=matches,
        budget_chars=budget_chars,
        answer_contract=_ANSWER_CONTRACT,
        max_chunk_chars=MAX_CHUNK_CHARS,
        recipe_chunk_chars=RECIPE_CHUNK_CHARS,
    )
