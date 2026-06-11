from __future__ import annotations

from dataclasses import dataclass


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
