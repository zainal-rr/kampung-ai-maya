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

import re
from dataclasses import dataclass
from pathlib import Path

from canonical_memory_text import memory_tokens

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_SKILL_DIR = REPO_ROOT / "maya_skills" / "active"

MAX_CONTEXT_CHARS = 6000
MAX_CHUNK_CHARS = 2600
RECIPE_CHUNK_CHARS = 5000
MAX_CHUNKS = 3
MIN_CHUNK_OVERLAP = 2
MIN_WEAK_HITS = 2

_CONFIG_WORDS = ("configure", "config", "create", "set up", "setup", "enable", "command", "cli", "deploy", "provision")
_DESIGN_WORDS = ("design", "topology", "architecture", "choose", "compare", "plan the", "layout")

_skills_cache: dict[str, tuple[tuple[tuple[str, float], ...], list["DomainSkill"]]] = {}
_chunk_cache: dict[str, tuple[float, list["KnowledgeChunk"]]] = {}


@dataclass(frozen=True)
class DomainSkill:
    skill_id: str
    name: str
    path: str
    kb_root: str
    retrieval_order: tuple[str, ...]
    strong_triggers: tuple[str, ...]
    weak_triggers: frozenset[str]
    non_triggers: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    header: str
    text: str
    tokens: frozenset[str]
    whole_file: bool = False


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
        skill = _parse_domain_skill(path)
        if skill:
            skills.append(skill)
    _skills_cache[str(directory)] = (stamps, skills)
    return skills


def detect_domain_skill(query: str, skills: list[DomainSkill]) -> DomainSkill | None:
    lowered = " ".join(str(query).lower().split())
    tokens = memory_tokens(lowered)
    best: tuple[int, DomainSkill] | None = None
    for skill in skills:
        strong_hits = [t for t in skill.strong_triggers if _word_match(t, lowered)]
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
    boosts = _directory_boosts(query, skill.retrieval_order)
    scored: list[tuple[float, int, KnowledgeChunk]] = []
    for index, chunk in enumerate(_kb_chunks(skill)):
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
    parts: list[str] = [f"Domain knowledge ({skill.name}):"]
    used = len(parts[0])
    for _score, chunk in matches:
        chunk_cap = RECIPE_CHUNK_CHARS if chunk.whole_file else MAX_CHUNK_CHARS
        body = chunk.text[:chunk_cap].rstrip()
        block = f"[source: {chunk.source} § {chunk.header}]\n{body}"
        if used + len(block) > budget_chars:
            break
        parts.append(block)
        used += len(block)
    if len(parts) == 1:
        return "", None
    parts.append(
        "Ground the answer in these sources and name the source recipe or doc used. "
        "If they do not cover the question, say the answer is unverified general knowledge."
    )
    return "\n\n".join(parts), skill


def _parse_domain_skill(path: Path) -> DomainSkill | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    sections = _markdown_sections(text)
    kb_section = _section(sections, "knowledge base")
    triggers_section = _section(sections, "trigger phrases")
    if not kb_section or not triggers_section:
        return None
    kb_paths = re.findall(r"`([^`]+/?)`", kb_section)
    kb_root = next((p.strip().rstrip("/") for p in kb_paths if "/" in p), "")
    if not kb_root or not (REPO_ROOT / kb_root).is_dir():
        return None
    retrieval_order = tuple(
        p.strip().rstrip("/")
        for p in kb_paths
        if p.strip().rstrip("/") != kb_root and p.strip().startswith(kb_root)
    )
    strong: list[str] = []
    weak: set[str] = set()
    non_triggers: list[str] = []
    for line in triggers_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- non-trigger:"):
            # Vetoes are phrase segments only ("home wi-fi", "consumer ...").
            # Single tokens are too dangerous: "consumer router help" must not
            # put "router" on the veto list.
            body = stripped.split(":", 1)[1]
            for segment in re.split(r",| or ", body):
                phrase = " ".join(segment.lower().split())
                if len(phrase) >= 4:
                    non_triggers.append(phrase)
        elif stripped.startswith("- trigger:"):
            body = stripped.split(":", 1)[1]
            terms = _strong_terms(body)
            strong.extend(terms)
            captured = memory_tokens(" ".join(terms))
            weak |= memory_tokens(body) - captured
    if not strong and not weak:
        return None
    title = text.splitlines()[0].lstrip("# ").strip() if text.splitlines() else path.stem
    return DomainSkill(
        skill_id=path.stem,
        name=title or path.stem,
        path=str(path),
        kb_root=kb_root,
        retrieval_order=retrieval_order,
        strong_triggers=tuple(dict.fromkeys(t.lower() for t in strong)),
        weak_triggers=frozenset(weak),
        non_triggers=tuple(dict.fromkeys(t.lower() for t in non_triggers)),
    )


def _strong_terms(body: str) -> list[str]:
    terms: list[str] = []
    terms.extend(re.findall(r'"([^"]+)"', body))
    for group in re.findall(r"\(([^)]+)\)", body):
        terms.extend(part.strip() for part in group.split(",") if part.strip())
    terms.extend(re.findall(r"\b[A-Z][A-Z0-9-]{1,}\b", body))
    return [t for t in terms if t]


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    header = ""
    lines: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+)$", line)
        if match:
            if header or lines:
                sections.append((header, "\n".join(lines).strip()))
            header, lines = match.group(1).strip(), []
        else:
            lines.append(line)
    if header or lines:
        sections.append((header, "\n".join(lines).strip()))
    return sections


def _section(sections: list[tuple[str, str]], name: str) -> str:
    for header, body in sections:
        if header.lower().startswith(name):
            return body
    return ""


def _kb_chunks(skill: DomainSkill) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    root = REPO_ROOT / skill.kb_root
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        key = str(path)
        mtime = path.stat().st_mtime
        cached = _chunk_cache.get(key)
        if cached and cached[0] == mtime:
            chunks.extend(cached[1])
            continue
        file_chunks = _chunk_file(path)
        _chunk_cache[key] = (mtime, file_chunks)
        chunks.extend(file_chunks)
    return chunks


def _chunk_file(path: Path) -> list[KnowledgeChunk]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    source = str(path.relative_to(REPO_ROOT))
    title = ""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break
    sections = _markdown_sections(text)
    headers = {header.lower().split(" ")[0] for header, _ in sections}
    is_recipe = "recipes" in path.parts or ("intent" in headers and "rollback" in headers)
    if is_recipe:
        # Worked recipes are retrieved whole: a config answer without its
        # verification/rollback (or method/limitations) sections breaks the
        # recipe contract. Anything under a recipes/ directory counts.
        return [
            KnowledgeChunk(
                source=source,
                header=title or path.stem,
                text=text.strip(),
                tokens=frozenset(memory_tokens(text)),
                whole_file=True,
            )
        ]
    chunks = []
    for header, body in _markdown_sections(text):
        if not body:
            continue
        label = f"{title}: {header}" if title and header else (header or title or path.stem)
        chunk_text = f"{label}\n{body}" if label else body
        chunks.append(
            KnowledgeChunk(
                source=source,
                header=header or title or path.stem,
                text=chunk_text,
                tokens=frozenset(memory_tokens(chunk_text)),
            )
        )
    return chunks


def _directory_boosts(query: str, retrieval_order: tuple[str, ...]) -> list[tuple[str, float]]:
    lowered = " ".join(str(query).lower().split())
    config_like = any(_word_match(word, lowered) for word in _CONFIG_WORDS)
    design_like = any(_word_match(word, lowered) for word in _DESIGN_WORDS)
    boosts: list[tuple[str, float]] = []
    for prefix in retrieval_order:
        name = prefix.lower()
        boost = 1.0
        if "recipe" in name and config_like:
            boost = 1.3
        elif "architect" in name and design_like:
            boost = 1.3
        elif "recipe" in name:
            boost = 1.1
        boosts.append((prefix, boost))
    return boosts


def _word_match(term: str, lowered_text: str) -> bool:
    term = term.strip().lower()
    if not term:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered_text))
