from __future__ import annotations

import os
import re

import aiosqlite

from maya_memory.canonical_memory_embeddings import EmbedCall
from maya_memory.canonical_memory import search_canonical_direct_fact, search_relevant_canonical_memories
from maya_memory.canonical_memory_text import subject_key_from_text
from maya_core.lesson_store import search_lessons
from maya_core.language_policy import is_language_topic, uses_malay_or_manglish, wants_malay_or_manglish
from maya_core.routine_store import list_routines
from maya_core.time_parser import format_local_time, weekday_name

STOPWORDS = {
    "what", "when", "with", "from", "that", "this", "have", "about", "into",
    "your", "will", "would", "there", "their", "them", "then", "just", "please",
}
SOURCE_WEIGHTS = {"imac": 5, "telegram": 4, "project": 3, "legacy": 2, "omi_transcript": 1}
INTERNAL_PREFERENCE_KEYS = {"telegram_chat_id"}


class MemoryService:
    def __init__(self, db_path: str, *, embedding_agent: EmbedCall | None = None):
        self.db_path = db_path
        self.embedding_agent = embedding_agent
        self.archive_enabled = os.getenv("ENABLE_ARCHIVE_MEMORY", "0") == "1"

    async def build_prompt_context(self, query: str, limit: int = 6) -> str:
        canonical = await search_relevant_canonical_memories(self.db_path, query, limit=3, embedding_agent=self.embedding_agent)
        lessons = await search_lessons(self.db_path, query, limit=3)
        preferences = await self._relevant_preferences(query, limit=3)
        memories = await self._relevant_knowledge(query, limit=limit) if self.archive_enabled else []
        tasks = await self._relevant_tasks(query, limit=3)
        routines = await self._relevant_routines(query, limit=3)

        sections = []
        if canonical:
            sections.append("Saved facts:\n" + "\n".join(f"- {item}" for item in canonical))
        if lessons:
            sections.append("Learned rules:\n" + "\n".join(f"- {item}" for item in lessons))
        if preferences:
            sections.append("Preferences:\n" + "\n".join(f"- {item}" for item in preferences))
        if tasks:
            sections.append("Open tasks:\n" + "\n".join(f"- {item}" for item in tasks))
        if routines:
            sections.append("Active routines:\n" + "\n".join(f"- {item}" for item in routines))
        if memories:
            sections.append("Relevant memory:\n" + "\n".join(f"- {item}" for item in memories))
        return "\n\n".join(sections)

    async def search(self, query: str, limit: int = 6) -> list[str]:
        canonical = await search_relevant_canonical_memories(self.db_path, query, limit=2, embedding_agent=self.embedding_agent)
        lessons = await search_lessons(self.db_path, query, limit=2)
        preferences = await self._relevant_preferences(query, limit=2)
        memories = await self._relevant_knowledge(query, limit=limit) if self.archive_enabled else []
        return canonical + lessons + preferences + memories

    async def search_preferences(self, query: str, limit: int = 6) -> list[str]:
        return await self._relevant_preferences(query, limit=limit)

    async def search_direct_fact(self, query: str, limit: int = 3) -> list[str]:
        subject = self._normalize_fact_subject(query)
        if not subject:
            return []
        canonical = await search_canonical_direct_fact(self.db_path, query, limit=limit, embedding_agent=self.embedding_agent)
        if canonical is None:
            return []
        if canonical:
            return canonical
        rows: list[str] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            pref_cursor = await db.execute(
                """
                SELECT value AS content
                FROM preferences
                ORDER BY updated_at DESC
                LIMIT 80
                """
            )
            rows.extend(str(row["content"]) for row in await pref_cursor.fetchall())
            lesson_cursor = await db.execute(
                """
                SELECT normalized_rule AS content
                FROM lessons
                ORDER BY created_at DESC
                LIMIT 80
                """
            )
            rows.extend(str(row["content"]) for row in await lesson_cursor.fetchall())
            try:
                curated_cursor = await db.execute(
                    """
                    SELECT content
                    FROM curated_memory_items
                    WHERE status = 'active'
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 80
                    """
                )
                rows.extend(str(row["content"]) for row in await curated_cursor.fetchall())
            except aiosqlite.OperationalError:
                pass
        matches: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if self._normalize_fact_subject(row) != subject:
                continue
            cleaned = " ".join(row.split())
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            matches.append(cleaned)
            if len(matches) >= limit:
                break
        return matches

    async def _relevant_preferences(self, query: str, limit: int) -> list[str]:
        tokens = self._tokens(query)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT key, value, source
                FROM preferences
                ORDER BY updated_at DESC
                LIMIT 20
                """
            )
            rows = await cursor.fetchall()

        scored = []
        language_context = (
            is_language_topic(query)
            or uses_malay_or_manglish(query)
            or wants_malay_or_manglish(query)
            or self._is_story_query(query)
        )
        for row in rows:
            if self._is_internal_preference(row["key"], row["value"]):
                continue
            value = row["value"]
            if not language_context and self._is_language_preference(row["key"], value):
                continue
            haystack = f"{row['key']} {value}"
            score = self._overlap_score(tokens, haystack)
            preference_key = row["key"].lower().startswith("pref_")
            if "telegram" in tokens and row["source"] == "telegram" and preference_key:
                score += 1
            if "style" in tokens and any(word in row["key"].lower() for word in ("style", "reply", "tone", "short")):
                score += 2
            if "reply" in tokens and "reply" in row["key"].lower():
                score += 2
            if self._is_story_query(query) and "story" in row["key"]:
                score += 3
            if self._is_story_query(query) and row["key"] == "pref_story_voice":
                score += 3
            if self._is_story_query(query) and "cerita" in value.lower():
                score += 2
            if score <= 0 and tokens:
                continue
            if score <= 0:
                score = 1
            scored.append((score, value))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [value for score, value in scored[:limit] if score > 0]

    async def _relevant_tasks(self, query: str, limit: int) -> list[str]:
        tokens = self._tokens(query)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT title, status, due_at, details
                FROM tasks
                WHERE status IN ('pending', 'running', 'awaiting_confirmation')
                ORDER BY priority DESC, created_at ASC
                LIMIT 20
                """
            )
            rows = await cursor.fetchall()

        scored = []
        for row in rows:
            haystack = f"{row['title']} {row['details']}"
            score = self._overlap_score(tokens, haystack)
            if score <= 0 and tokens:
                continue
            due_text = f" due {row['due_at']}" if row["due_at"] else ""
            scored.append((score, f"{row['title']} ({row['status']}){due_text}"))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [value for _, value in scored[:limit]]

    async def _relevant_routines(self, query: str, limit: int) -> list[str]:
        lowered = query.lower()
        wants_routines = any(word in lowered for word in ("routine", "briefing", "recap", "reflection"))
        routines = await list_routines(self.db_path, active_only=True, limit=12)
        if not wants_routines:
            return []

        described = [self._describe_routine(item) for item in routines[:limit]]
        return described or ["No active routines."]

    async def _relevant_knowledge(self, query: str, limit: int) -> list[str]:
        tokens = self._tokens(query)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT category, content, tags
                FROM knowledge_base
                ORDER BY id DESC
                LIMIT 120
                """
            )
            rows = await cursor.fetchall()

        scored = []
        for row in rows:
            haystack = f"{row['content']} {row['tags']}"
            overlap = self._overlap_score(tokens, haystack)
            source_weight = SOURCE_WEIGHTS.get(row["category"], 1)
            if overlap <= 0 and tokens:
                continue
            score = overlap + source_weight
            scored.append((score, row["content"]))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [value for _, value in scored[:limit]]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"\b[a-z0-9]{4,}\b", text.lower())
            if token not in STOPWORDS
        }

    @staticmethod
    def _normalize_fact_subject(text: str) -> str:
        # Delegate to the canonical normalizer so the preference/lesson/curated
        # fallback agrees with canonical memory. The old local version turned
        # "what is my favourite snack" into subject "what", so question-form
        # queries could never match stored rows in the fallback path.
        return subject_key_from_text(text)

    @staticmethod
    def _overlap_score(tokens: set[str], haystack: str) -> int:
        if not tokens:
            return 0
        lowered = haystack.lower()
        return sum(1 for token in tokens if token in lowered)

    @staticmethod
    def _is_story_query(query: str) -> bool:
        lowered = query.lower()
        return any(marker in lowered for marker in ("story", "cerita", "karang"))

    @staticmethod
    def _describe_routine(item: dict[str, str | int | None]) -> str:
        when = f"every day at {format_local_time(str(item['local_time']))}"
        if item["weekday"] is not None:
            when = f"every {weekday_name(item['weekday'])} at {format_local_time(str(item['local_time']))}"
        return f"{item['name']} on {item['channel']} {when}"

    @staticmethod
    def _is_internal_preference(key: str, value: str) -> bool:
        lowered = key.lower()
        if lowered in INTERNAL_PREFERENCE_KEYS:
            return True
        if lowered.endswith("_chat_id"):
            return True
        if "chat_id" in lowered and value.isdigit():
            return True
        value_lower = str(value).lower().strip()
        if value_lower.startswith("/users/") or "/desktop/maya/" in value_lower:
            return True
        if any(ext in value_lower for ext in (".md", ".docx", ".pptx", ".xlsx", ".svg", ".png", ".jpg", ".pdf")):
            return True
        return False

    @staticmethod
    def _is_language_preference(key: str, value: str) -> bool:
        lowered = f"{key} {value}".lower()
        return any(word in lowered for word in ("malay", "manglish", "melayu", "bahasa"))
