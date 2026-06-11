from __future__ import annotations

from pathlib import Path

from canonical_memory_text import memory_tokens
from domain_knowledge_models import DomainSkill, KnowledgeChunk
from domain_knowledge_parse import markdown_sections, word_match

CONFIG_WORDS = ("configure", "config", "create", "set up", "setup", "enable", "command", "cli", "deploy", "provision")
DESIGN_WORDS = ("design", "topology", "architecture", "choose", "compare", "plan the", "layout")


def directory_boosts(query: str, retrieval_order: tuple[str, ...]) -> list[tuple[str, float]]:
    lowered = " ".join(str(query).lower().split())
    config_like = any(word_match(word, lowered) for word in CONFIG_WORDS)
    design_like = any(word_match(word, lowered) for word in DESIGN_WORDS)
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


def kb_chunks(
    skill: DomainSkill,
    repo_root: Path,
    chunk_cache: dict[str, tuple[float, list[KnowledgeChunk]]],
) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    root = repo_root / skill.kb_root
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        key = str(path)
        mtime = path.stat().st_mtime
        cached = chunk_cache.get(key)
        if cached and cached[0] == mtime:
            chunks.extend(cached[1])
            continue
        file_chunks = chunk_file(path, repo_root)
        chunk_cache[key] = (mtime, file_chunks)
        chunks.extend(file_chunks)
    return chunks


def chunk_file(path: Path, repo_root: Path) -> list[KnowledgeChunk]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    source = str(path.relative_to(repo_root))
    title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), "")
    sections = markdown_sections(text)
    headers = {header.lower().split(" ")[0] for header, _ in sections}
    is_recipe = "recipes" in path.parts or ("intent" in headers and "rollback" in headers)
    if is_recipe:
        return [
            KnowledgeChunk(
                source=source,
                header=title or path.stem,
                text=text.strip(),
                tokens=frozenset(memory_tokens(text)),
                whole_file=True,
            )
        ]
    chunks: list[KnowledgeChunk] = []
    for header, body in sections:
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
