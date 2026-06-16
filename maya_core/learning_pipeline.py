from __future__ import annotations

import re

from maya_core.lesson_store import (
    add_lesson,
    add_pending_lesson,
    clear_pending_lesson,
    get_lesson,
    get_pending_lesson,
    list_lessons,
)
from maya_core.assistant_command_helpers import is_user_visible_memory
from maya_memory.canonical_memory import upsert_canonical_memory
from maya_memory.memory_extraction import (
    ProviderCall,
    default_extraction_agent,
    extract_for_save,
    live_extraction_enabled,
)
from maya_memory.memory_perspective import normalize_user_perspective_memory
from maya_core.permission_policy import contains_sensitive_info, hard_no_private_exposure_text
from maya_core.self_improvement_policy import verified_learning_message
from storage import get_preference, upsert_preference
from storage import list_preferences


class LearningPipeline:
    def __init__(
        self,
        db_path: str,
        extraction_agent: ProviderCall | None = None,
        extraction_live: bool | None = None,
    ):
        self.db_path = db_path
        # Env-gated structured extraction; None keeps today's regex behavior.
        # Shadow mode: agent present + extraction_live False -> provider runs
        # and divergence is audited, but the deterministic parse is saved.
        if extraction_agent is not None:
            self.extraction_agent = extraction_agent
            self.extraction_live = True if extraction_live is None else extraction_live
        else:
            self.extraction_agent = default_extraction_agent()
            self.extraction_live = (
                extraction_live if extraction_live is not None else live_extraction_enabled()
            )

    async def handle(self, text: str, channel: str) -> str | None:
        clean = text.strip()
        decision = self._decision(clean)
        if decision:
            return await self._resolve_pending(decision, channel)
        if self._is_lesson_inspection(clean):
            return await self._inspect_lessons()
        explicit = self._explicit_lesson(clean)
        if explicit:
            if contains_sensitive_info(explicit[0]):
                return hard_no_private_exposure_text()
            return await self._save_explicit(clean, channel, *explicit)
        implicit = self._implicit_lesson(clean)
        if implicit:
            return await self._ask_to_save(clean, channel, *implicit)
        return None

    async def _save_explicit(
        self,
        raw_text: str,
        channel: str,
        rule: str,
        lesson_type: str,
        scope: str,
    ) -> str:
        extraction = await extract_for_save(
            self.db_path, rule, self.extraction_agent, live=self.extraction_live
        )
        echo = ""
        if extraction.source == "provider":
            if extraction.sensitive:
                return hard_no_private_exposure_text()
            lesson_type = extraction.kind
            scope = extraction.scope
            # Visibility contract: when extraction shaped the save, the reply
            # must echo the parsed subject and value so a wrong parse is
            # noticed immediately.
            echo = f" (saved as {extraction.subject} -> {extraction.value})"
        preference_key = self._preference_key(scope, rule)
        await upsert_preference(self.db_path, preference_key, rule, source=channel)
        lesson_id = await add_lesson(
            self.db_path,
            raw_text,
            rule,
            lesson_type,
            scope,
            trigger="explicit",
            confidence="high",
            channel=channel,
            preference_key=preference_key,
        )
        await upsert_canonical_memory(
            self.db_path,
            raw_text=raw_text,
            content=rule,
            kind=lesson_type,
            scope=scope,
            source_channel=channel,
            confidence="high",
        )
        if not await self._verified(lesson_id, preference_key, rule):
            return "I tried to save that, but I could not verify it yet."
        return f"{verified_learning_message('preference', True)} {rule}{echo}"

    async def _ask_to_save(
        self,
        raw_text: str,
        channel: str,
        rule: str,
        lesson_type: str,
        scope: str,
    ) -> str:
        await add_pending_lesson(self.db_path, raw_text, rule, lesson_type, scope, channel)
        return f"I can remember that as a {scope} preference. Do you want me to save it?"

    async def _resolve_pending(self, decision: str, channel: str) -> str | None:
        pending = await get_pending_lesson(self.db_path, channel)
        if not pending:
            return None
        pending_id = int(pending["id"])
        if decision == "decline":
            await clear_pending_lesson(self.db_path, pending_id)
            return "Okay. I will not save that."
        if decision == "later":
            await clear_pending_lesson(self.db_path, pending_id)
            return "Okay. I will leave that unsaved for now."
        rule = str(pending["normalized_rule"])
        key = self._preference_key(str(pending["scope"]), rule)
        await upsert_preference(self.db_path, key, rule, source=channel)
        lesson_id = await add_lesson(
            self.db_path,
            str(pending["raw_text"]),
            rule,
            str(pending["lesson_type"]),
            str(pending["scope"]),
            trigger="confirmed",
            confidence="medium",
            channel=channel,
            preference_key=key,
        )
        await upsert_canonical_memory(
            self.db_path,
            raw_text=str(pending["raw_text"]),
            content=rule,
            kind=str(pending["lesson_type"]),
            scope=str(pending["scope"]),
            source_channel=channel,
            confidence="medium",
        )
        await clear_pending_lesson(self.db_path, pending_id)
        if not await self._verified(lesson_id, key, rule):
            return "I tried to save that, but I could not verify it yet."
        return f"{verified_learning_message('preference', True)} {rule}"

    async def _inspect_lessons(self) -> str:
        lessons = [
            item for item in await list_lessons(self.db_path, limit=10)
            if self._visible_lesson(str(item["normalized_rule"]))
        ][:6]
        if not lessons:
            preferences = await self._visible_preferences()
            if not preferences:
                return "I have not logged any lessons yet."
            lines = [f"{idx}) {item}" for idx, item in enumerate(preferences[:5], start=1)]
            return (
                "I have saved preferences, but no lesson-log entries yet. "
                "Here are the preferences I can use:\n" + "\n".join(lines)
            )
        lines = [f"{idx}) {item['normalized_rule']}" for idx, item in enumerate(lessons, start=1)]
        return "Here is what I have learned recently:\n" + "\n".join(lines)

    async def _visible_preferences(self) -> list[str]:
        preferences = await list_preferences(self.db_path, limit=10)
        return [
            str(item["value"])
            for item in preferences
            if "chat_id" not in str(item["key"]).lower()
            and is_user_visible_memory(str(item["value"]))
        ]

    @staticmethod
    def _visible_lesson(rule: str) -> bool:
        lowered = rule.lower().strip()
        if lowered == "you are maya, you are the one who see":
            return False
        return is_user_visible_memory(rule)

    async def _verified(self, lesson_id: int, preference_key: str, rule: str) -> bool:
        lesson = await get_lesson(self.db_path, lesson_id)
        preference = await get_preference(self.db_path, preference_key)
        return bool(lesson and lesson.get("normalized_rule") == rule and preference == rule)

    def _explicit_lesson(self, text: str) -> tuple[str, str, str] | None:
        lowered = text.lower().strip()
        for pattern in (
            r"^i(?: am|'m) teaching you(?: that)?\s+(.+)$",
            r"^my preference(?: for you)?(?: is)?\s+(.+)$",
            r"^remember(?:\s+that)?[\s,;:]+(.+)$",
        ):
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                return self._normalize_rule(match.group(1).strip(), lowered)
        if self._is_direct_test_fact(text, lowered):
            return self._normalize_rule(text.strip(), lowered)
        return None

    def _implicit_lesson(self, text: str) -> tuple[str, str, str] | None:
        lowered = text.lower()
        markers = (
            "too formal",
            "too robotic",
            "too long",
            "too structured",
            "that sounds weird",
            "the structure is weird",
            "i don't like",
            "i dont like",
            "i don't like how",
            "don't use",
            "dont use",
            "do not use",
            "please avoid",
            "makes me anxious",
            "should sound",
            "should be more",
            "not like that",
        )
        if not any(marker in lowered for marker in markers):
            return None
        return self._normalize_rule(text.strip(), lowered)

    @staticmethod
    def _is_direct_test_fact(text: str, lowered: str) -> bool:
        if not any(marker in f" {lowered} " for marker in (" test ", " regression ", " temporary ")):
            return False
        return bool(re.match(r"^my\s+.+?\s+(?:is|are|=)\s+.+$", text, re.IGNORECASE))

    @staticmethod
    def _normalize_rule(text: str, lowered: str) -> tuple[str, str, str]:
        text = normalize_user_perspective_memory(text)
        lowered = text.lower()
        if any(word in lowered for word in ("cerita", "story", "karang", "essay")):
            return (
                "For cerita or story replies, use flowing paragraph form and natural local rhythm.",
                "style",
                "story",
            )
        if any(word in lowered for word in ("manglish", "malay", "melayu", "bahasa")):
            return (
                "For Malay or Manglish, keep it concise, natural, lightly code switched, and local.",
                "style",
                "language",
            )
        if any(word in lowered for word in ("dash", "hyphen")):
            return ("Do not use dash symbols in replies.", "style", "punctuation")
        if any(word in lowered for word in ("exclamation", "tanda seru", "!")):
            return ("Do not use exclamation marks in replies.", "style", "punctuation")
        if "too formal" in lowered:
            return ("Keep replies less formal and more natural.", "style", "tone")
        if "too robotic" in lowered:
            return ("Keep replies more human, warm, and natural.", "style", "tone")
        if "too long" in lowered:
            return ("Keep replies shorter unless the task is complex.", "style", "brevity")
        if "too structured" in lowered or "structure is weird" in lowered:
            return ("Use structure only when it helps readability.", "style", "structure")
        return (text, "preference", "global")

    @staticmethod
    def _decision(text: str) -> str | None:
        lowered = text.lower().strip().rstrip("?.! ")
        if lowered in {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "go ahead", "save it"}:
            return "approve"
        if lowered in {"no", "n", "nope", "cancel", "stop", "don't save it", "dont save it"}:
            return "decline"
        if lowered in {"later", "not now"}:
            return "later"
        return None

    @staticmethod
    def _is_lesson_inspection(text: str) -> bool:
        lowered = text.lower().strip().rstrip("?.! ")
        return lowered in {
            "what did you learn",
            "what did you learn from me",
            "what did you learn from me today",
            "show recent lessons",
            "show my lessons",
            "what lessons did you save",
        }

    @staticmethod
    def _preference_key(scope: str, rule: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", f"{scope}_{rule.lower()}").strip("_")
        return f"lesson_{slug[:48] or 'note'}"
