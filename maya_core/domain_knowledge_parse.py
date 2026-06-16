from __future__ import annotations

import re
from pathlib import Path

from maya_memory.canonical_memory_text import memory_tokens
from domain_knowledge_models import DomainSkill


def parse_domain_skill(path: Path, repo_root: Path) -> DomainSkill | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    sections = markdown_sections(text)
    kb_section = section(sections, "knowledge base")
    triggers_section = section(sections, "trigger phrases")
    if not kb_section or not triggers_section:
        return None
    kb_paths = re.findall(r"`([^`]+/?)`", kb_section)
    kb_root = next((p.strip().rstrip("/") for p in kb_paths if "/" in p), "")
    if not kb_root or not (repo_root / kb_root).is_dir():
        return None
    retrieval_order = tuple(
        p.strip().rstrip("/")
        for p in kb_paths
        if p.strip().rstrip("/") != kb_root and p.strip().startswith(kb_root)
    )
    strong, weak, non_triggers = trigger_terms(triggers_section)
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


def trigger_terms(triggers_section: str) -> tuple[list[str], set[str], list[str]]:
    strong: list[str] = []
    weak: set[str] = set()
    non_triggers: list[str] = []
    for line in triggers_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- non-trigger:"):
            body = stripped.split(":", 1)[1]
            for segment in re.split(r",| or ", body):
                phrase = " ".join(segment.lower().split())
                if len(phrase) >= 4:
                    non_triggers.append(phrase)
        elif stripped.startswith("- trigger:"):
            body = stripped.split(":", 1)[1]
            terms = strong_terms(body)
            strong.extend(terms)
            weak |= memory_tokens(body) - memory_tokens(" ".join(terms))
    return strong, weak, non_triggers


def strong_terms(body: str) -> list[str]:
    terms: list[str] = []
    terms.extend(re.findall(r'"([^"]+)"', body))
    for group in re.findall(r"\(([^)]+)\)", body):
        terms.extend(part.strip() for part in group.split(",") if part.strip())
    terms.extend(re.findall(r"\b[A-Z][A-Z0-9-]{1,}\b", body))
    return [t for t in terms if t]


def markdown_sections(text: str) -> list[tuple[str, str]]:
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


def section(sections: list[tuple[str, str]], name: str) -> str:
    for header, body in sections:
        if header.lower().startswith(name):
            return body
    return ""


def word_match(term: str, lowered_text: str) -> bool:
    term = term.strip().lower()
    if not term:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered_text))
