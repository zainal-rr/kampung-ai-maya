from __future__ import annotations

import re


class ResponsePolicy:
    def reply(self, text: str, channel: str) -> str | None:
        normalized = self._normalize(text)
        for handler in (
            self._topic_break_reply,
            self._greeting_reply,
            self._malay_reply,
            self._identity_reply,
            self._powering_reply,
            self._channel_role_reply,
            self._capability_reply,
            self._improvement_reply,
            self._scope_reply,
            self._needs_reply,
            self._goal_reply,
        ):
            reply = handler(normalized, channel)
            if reply is not None:
                return reply
        return None

    @staticmethod
    def _normalize(text: str) -> str:
        lowered = text.lower().strip()
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.rstrip("?.! ")

    @classmethod
    def is_topic_break(cls, text: str) -> bool:
        normalized = cls._normalize(text)
        return normalized in {
            "new topic",
            "fresh topic",
            "switch topic",
            "change topic",
            "let's change topic",
            "lets change topic",
            "let's talk about something else",
            "lets talk about something else",
        }

    @classmethod
    def _topic_break_reply(cls, text: str, channel: str) -> str | None:
        if not cls.is_topic_break(text):
            return None
        return "Okay. Fresh topic."

    @staticmethod
    def _greeting_reply(text: str, channel: str) -> str | None:
        greetings = {"hello", "hello maya", "hi", "hi maya", "hey", "hey maya"}
        if text not in greetings:
            return None
        if channel == "imac":
            return "Hey. I'm here."
        return "Hey. I'm here. What do you need?"

    @staticmethod
    def _malay_reply(text: str, channel: str) -> str | None:
        markers = {
            "can you speak in malay",
            "can you speak in manglish",
            "boleh cakap melayu",
            "boleh cakap manglish",
            "can you reply in malay",
            "can you reply in manglish",
        }
        if text not in markers:
            return None
        return (
            "Can, no problem. Lagi senang sembang macam ni, kan? "
            "Rasa more natural and chill for Kampung AI. So, mana part you nak kita go through first?"
        )

    @staticmethod
    def _identity_reply(text: str, channel: str) -> str | None:
        if text not in {"who are you", "what are you", "who is maya"}:
            return None
        return (
            "I'm Maya. Different systems can help behind the scenes depending on the task, "
            "but the voice on the surface stays the same."
        )

    @staticmethod
    def _powering_reply(text: str, channel: str) -> str | None:
        power_markers = (
            "what ai is powering you",
            "what ai powers you",
            "what model is powering you",
            "what model are you using",
            "what powers you",
            "what engine are you using",
        )
        if not any(marker in text for marker in power_markers):
            return None
        if channel == "telegram":
            return (
                "A few different engines can sit behind me depending on the task. "
                "On Telegram you're usually getting my text and research lane, but you're still talking to Maya."
            )
        return (
            "A few different systems can help behind the scenes depending on the task, "
            "but you're still talking to Maya."
        )

    @staticmethod
    def _channel_role_reply(text: str, channel: str) -> str | None:
        if "telegram" in text and "secondary" in text:
            return (
                "Telegram stays secondary because the iMac is Maya's main body. "
                "Telegram works best as the remote text and follow-up lane while the iMac stays the faster, "
                "more private place for local presence."
            )
        if "imac" in text and any(word in text for word in ("primary", "main body", "main channel")):
            return (
                "The iMac stays primary because that's where Maya is meant to feel present: "
                "faster, more private, and better for live interaction than a remote chat thread."
            )
        if "telegram" in text and any(phrase in text for phrase in ("used for", "use telegram", "telegram be used")):
            return (
                "Telegram is best for remote chat, research-style questions, follow-ups, memory checks, "
                "and task or routine updates when you're away from the iMac."
            )
        return None

    @staticmethod
    def _capability_reply(text: str, channel: str) -> str | None:
        capability_markers = {
            "what can you do",
            "what are you able to do",
            "what do you do",
            "what can you do for me on telegram right now",
            "what can you do on telegram right now",
        }
        if text not in capability_markers:
            return None
        if channel == "telegram":
            return (
                "On Telegram I can answer questions, remember preferences, track tasks and routines, "
                "summarize things, and handle research-style chat. Heavier strategy or coding can route deeper when needed."
            )
        return (
            "I can hold a conversation, remember context, manage tasks and routines, "
            "and help with local actions when they're enabled."
        )

    @staticmethod
    def _improvement_reply(text: str, channel: str) -> str | None:
        markers = (
            "how to make kampung ai better",
            "how can kampung ai be better",
            "what improvements can be made to kampung ai",
            "improvements that can be made",
            "improvement that can be made",
            "check the idea of kampung ai",
        )
        if not any(marker in text for marker in markers):
            return None
        return (
            "1) Core experience\n"
            "a) make Maya feel faster and more natural on the iMac and Telegram\n"
            "b) improve follow up understanding, memory use, and Malay or Manglish nuance\n\n"
            "2) Reliability\n"
            "a) make tasks, routines, and Telegram behavior more dependable\n"
            "b) keep the system simple before adding more surfaces\n\n"
            "3) Scope\n"
            "a) keep it personal first\n"
            "b) leave multi user or community features for a later product phase"
        )

    @staticmethod
    def _scope_reply(text: str, channel: str) -> str | None:
        markers = (
            "when is kampung ai an application that can be use by other people",
            "when is kampung ai an application that can be used by other people",
            "when is kampung ai for other people",
            "when does kampung ai become for other people",
            "when is kampung ai an app for other people",
        )
        if not any(marker in text for marker in markers):
            return None
        return (
            "1) Right now\n"
            "a) Kampung AI should stay your system, not a general app\n\n"
            "2) Before it becomes broader\n"
            "a) Maya works reliably for you first\n"
            "b) the memory and privacy model are clear\n"
            "c) the product stops depending on personal assumptions\n\n"
            "Only after that does it make sense to think about other people."
        )

    @staticmethod
    def _goal_reply(text: str, channel: str) -> str | None:
        asks_name = "your name" in text or text == "tell me your name"
        asks_goal = "your goal" in text or "your goals" in text or "your objective" in text or "your objectives" in text
        if not asks_goal and not (asks_name and "goal" in text):
            return None
        if asks_name:
            return (
                "I'm Maya. My goal is to be your reliable operating partner across the iMac, Telegram, "
                "memory, tasks, and routines without turning into noise."
            )
        return (
            "My goal is to be your reliable operating partner across the iMac, Telegram, memory, tasks, "
            "and routines without turning into noise."
        )

    @staticmethod
    def _needs_reply(text: str, channel: str) -> str | None:
        need_markers = (
            "what do you need to reach your goal",
            "what do you need to reach your goals",
            "what do you need to reach your objective",
            "what do you need to reach your objectives",
            "what do you need to reach your goal and objectives",
            "what do you need to reach your goals and objectives",
        )
        if not any(marker in text for marker in need_markers):
            return None
        return (
            "Mostly three things: live provider keys for the full voice and realtime path, "
            "stronger long-term follow-through across sessions, and more day-to-day use so I can get sharper where it matters."
        )
