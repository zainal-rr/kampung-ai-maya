from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re


GREETING_WORDS = frozenset({"hey", "hi", "hello", "okay", "ok", "yo"})
REFERENCE_START_RE = re.compile(r"^(?:is|was|were|has|had|will|looks|sounds|seems|appears)\b", re.IGNORECASE)
WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?|\d+", re.IGNORECASE)
STRIP_LEADING_RE = re.compile(r"^[\s,.:;!?-]+")
CLOSE_HOLD_RE = re.compile(
    r"\b("
    r"thank\s+you\s+maya|thanks\s+maya|that'?s\s+all\s+maya|"
    r"maya\s+you\s+can\s+stop|maya\s+stop\s+listening|"
    r"you\s+can\s+stop\s+listening|we'?re\s+done\s+maya"
    r")\b",
    re.IGNORECASE,
)
STANDALONE_CLOSE_RE = re.compile(r"^\s*(?:ok|okay|done|all\s+good)\s+maya[\s.!?]*$", re.IGNORECASE)


@dataclass(frozen=True)
class MeetAddressDecision:
    status: str
    remainder: str
    confidence: float = 0.0
    reason_code: str = "not_addressed"

    @property
    def addressed(self) -> bool:
        return self.status == "addressed"


@dataclass
class MeetConversationHold:
    idle_seconds: float = 180.0
    opened_at: float | None = None
    last_activity_at: float | None = None
    close_reason: str = ""

    def active(self, now: float) -> bool:
        if self.last_activity_at is None:
            return False
        if now - self.last_activity_at > self.idle_seconds:
            self.close("idle_timeout")
            return False
        return True

    def open(self, now: float) -> None:
        if self.opened_at is None:
            self.opened_at = now
        self.last_activity_at = now
        self.close_reason = ""

    def refresh(self, now: float) -> None:
        if self.opened_at is None:
            self.opened_at = now
        self.last_activity_at = now
        self.close_reason = ""

    def close(self, reason: str) -> None:
        self.opened_at = None
        self.last_activity_at = None
        self.close_reason = str(reason or "closed")


def is_hold_close_phrase(text: str) -> bool:
    value = str(text or "")
    return bool(CLOSE_HOLD_RE.search(value) or STANDALONE_CLOSE_RE.search(value))


def meet_address_decision(text: str) -> MeetAddressDecision:
    raw = str(text or "")
    tokens = _word_tokens(raw)
    if not tokens:
        return MeetAddressDecision("not_addressed", raw.strip(), 0.0, "not_addressed_empty")
    offset = 0
    if tokens[0][0].casefold() in GREETING_WORDS:
        offset = 1
    if offset >= len(tokens):
        return MeetAddressDecision("not_addressed", raw.strip(), 0.0, "not_addressed_greeting_only")
    exact = _exact_address(raw, tokens, offset)
    if exact is not None:
        return exact
    fuzzy = _fuzzy_address(raw, tokens, offset)
    if fuzzy is not None:
        return fuzzy
    return MeetAddressDecision("not_addressed", raw.strip(), 0.0, "not_addressed")


def addressed_to_maya(text: str) -> bool:
    return meet_address_decision(text).addressed


def strip_maya_address(text: str) -> str:
    decision = meet_address_decision(text)
    return decision.remainder if decision.addressed else str(text or "").strip()


def decision_from_audio_wake(text: str, *, confidence: float, delay_seconds: float) -> MeetAddressDecision:
    return MeetAddressDecision(
        "addressed",
        str(text or "").strip(),
        confidence=max(0.0, min(1.0, confidence)),
        reason_code="audio_wake_matched_transcript",
    )


def _exact_address(raw: str, tokens: list[tuple[str, int, int]], offset: int) -> MeetAddressDecision | None:
    word, _start, end = tokens[offset]
    if word.casefold() != "maya":
        return None
    remainder = _drop_repeated_address(_remainder(raw, end))
    if not remainder or REFERENCE_START_RE.match(remainder):
        return MeetAddressDecision("not_addressed", raw.strip(), 0.0, "not_addressed_reference")
    reason = "addressed_exact"
    if offset > 0:
        reason = "addressed_greeting_exact"
    return MeetAddressDecision("addressed", remainder, 1.0, reason)


def _fuzzy_address(raw: str, tokens: list[tuple[str, int, int]], offset: int) -> MeetAddressDecision | None:
    best: tuple[float, int] | None = None
    # Use one- and two-word spans from the beginning only. This catches ASR
    # wake mangles like "may i" or "my a" without waking on arbitrary mentions.
    for span in (1, 2):
        end_index = offset + span - 1
        if end_index >= len(tokens):
            continue
        words = [token[0] for token in tokens[offset : offset + span]]
        score = _wake_similarity(words)
        if score < 0.74:
            continue
        if best is None or score > best[0]:
            best = (score, span)
    if best is None:
        return None
    score, span = best
    end = tokens[offset + span - 1][2]
    remainder = _drop_repeated_address(_remainder(raw, end))
    if not remainder or REFERENCE_START_RE.match(remainder):
        return MeetAddressDecision("not_addressed", raw.strip(), 0.0, "not_addressed_reference")
    reason = "addressed_fuzzy"
    compact = _compact_words(token[0] for token in tokens[offset : offset + span])
    if compact not in {"maya", "mayya"}:
        reason = "addressed_wake_mangle"
    return MeetAddressDecision("addressed", remainder, score, reason)


def _wake_similarity(words) -> float:
    compact = _wake_compact_words(words)
    if not compact or not compact.startswith("m"):
        return 0.0
    if not _wake_like_shape(compact):
        return 0.0
    if compact.startswith("maybe"):
        return 0.0
    phonetic = _phonetic(compact)
    targets = ("maya", "maia", "mya", "mai")
    score = max(
        SequenceMatcher(a=compact, b=target).ratio()
        for target in targets
    )
    score = max(
        score,
        max(SequenceMatcher(a=phonetic, b=_phonetic(target)).ratio() for target in targets),
    )
    if compact in {"may", "my"}:
        # Too common as standalone English openers; two-token spans can still
        # recover "may i" and "my a".
        return min(score, 0.55)
    return score


def _drop_repeated_address(remainder: str) -> str:
    cleaned = str(remainder or "").strip()
    for _ in range(3):
        tokens = _word_tokens(cleaned)
        if not tokens:
            return cleaned
        offset = 1 if tokens[0][0].casefold() in GREETING_WORDS else 0
        if offset >= len(tokens):
            return cleaned
        end = _leading_address_end(tokens, offset)
        if end is None:
            return cleaned
        next_cleaned = _remainder(cleaned, end)
        if not next_cleaned or REFERENCE_START_RE.match(next_cleaned):
            return cleaned
        cleaned = next_cleaned
    return cleaned


def _leading_address_end(tokens: list[tuple[str, int, int]], offset: int) -> int | None:
    if tokens[offset][0].casefold() == "maya":
        return tokens[offset][2]
    best: tuple[float, int] | None = None
    for span in (1, 2):
        end_index = offset + span - 1
        if end_index >= len(tokens):
            continue
        score = _wake_similarity(token[0] for token in tokens[offset : offset + span])
        if score >= 0.74 and (best is None or score > best[0]):
            best = (score, span)
    return None if best is None else tokens[offset + best[1] - 1][2]


def _wake_like_shape(compact: str) -> bool:
    # Keep this as a phonetic shape check rather than a phrase list: ASR wake
    # mangles should be short and made from Maya-like vowel/y sounds, not
    # arbitrary M-words such as "mail", "mayo", or "mama".
    if len(compact) < 3 or len(compact) > 5:
        return False
    if re.fullmatch(r"[maiye]+", compact) is None:
        return False
    tail = compact[1:]
    return any(char in tail for char in "iye")


def _phonetic(value: str) -> str:
    value = value.casefold()
    value = value.replace("y", "i")
    value = value.replace("e", "a")
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def _compact_words(words) -> str:
    return re.sub(r"[^a-z0-9]+", "", "".join(str(word).casefold() for word in words))


def _wake_compact_words(words) -> str:
    normalized: list[str] = []
    for raw in words:
        word = re.sub(r"[^a-z0-9]+", "", str(raw).casefold())
        if not word:
            continue
        if word == "and" and normalized and normalized[0] in {"my", "may", "mai"}:
            # Recall ASR has produced "hello my and..." for "Hello Maya...".
            # Treat this as a vowel-like wake fragment only in the leading
            # wake slot; request-shaped speech still cannot wake Maya alone.
            normalized.append("a")
        else:
            normalized.append(word)
    return _compact_words(normalized)


def _word_tokens(raw: str) -> list[tuple[str, int, int]]:
    return [(match.group(0), match.start(), match.end()) for match in WORD_RE.finditer(raw)]


def _remainder(raw: str, start: int) -> str:
    return STRIP_LEADING_RE.sub("", raw[start:]).strip()
