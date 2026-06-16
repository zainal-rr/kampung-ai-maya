from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from assistant_text import strip_wake_prefix
from document_request_parser import document_request
from voice_transcript_policy import clean_voice_transcript_for_intent


TOPICS = (
    "two day Seoul food trip",
    "router setup guide",
    "Kampung AI document quality proposal",
    "monthly office spending tracker",
    "Seoul food budget",
    "Kampung AI roadmap",
    "weekly office priorities",
    "Penang hotel comparison",
    "client meeting notes",
    "home WiFi upgrade plan",
    "Tokyo cafe itinerary",
    "project launch checklist",
)

FORBIDDEN_TOPIC_NOISE = (
    "put it",
    "needs to be",
    "should be",
    "has to be",
    "must be",
    "may i",
    "hey maya",
    "hey, may i",
)


def main() -> None:
    cases = _build_cases()
    failures: list[str] = []
    for index, case in enumerate(cases, start=1):
        transcript, expected_kind = case
        cleaned = clean_voice_transcript_for_intent(strip_wake_prefix(transcript))
        parsed = document_request(cleaned)
        if not parsed:
            failures.append(f"{index}: no parse | {transcript!r} -> {cleaned!r}")
            continue
        kind, topic, _ = parsed
        if kind != expected_kind:
            failures.append(f"{index}: kind {kind!r} != {expected_kind!r} | {transcript!r} -> {parsed!r}")
            continue
        lowered_topic = topic.lower()
        noise = [item for item in FORBIDDEN_TOPIC_NOISE if item in lowered_topic]
        if noise:
            failures.append(f"{index}: topic noise {noise!r} | {transcript!r} -> {parsed!r}")
    if failures:
        raise AssertionError("\n".join(failures[:20]))
    print(f"voice_artifact_transcript_replay_500: ok ({len(cases)} cases)")


def _build_cases() -> list[tuple[str, str]]:
    cases: list[tuple[str, str]] = []
    cases.extend(_docx_cases())
    cases.extend(_xlsx_cases())
    cases.extend(_pptx_cases())
    if len(cases) < 500:
        raise AssertionError(f"not enough cases: {len(cases)}")
    return cases[:500]


def _docx_cases() -> list[tuple[str, str]]:
    templates = (
        "Hey Maya, make me a {topic} Word document.",
        "Hey, may I make me a {topic}? It needs to be in Word.",
        "I need a {topic}. Put it in Word.",
        "Can you write a {topic} in Word?",
        "Could you make me a Word document about {topic}?",
        "Please put together a {topic} Word document.",
        "um Hey Maya, make me a {topic}. It should be in Word.",
        "no wait make me a {topic}; it has to be a Word document.",
        "Can you can you create a {topic} docx?",
        "Hey Maya, create a {topic}, with background noise, it must be in Word.",
        "Make me a {topic}. Write it as a Word document.",
        "I want you to draft a {topic} as a Word document.",
        "Help me create a {topic} Word document.",
        "Hey Maya, make me a {topic}. Keep it in Word.",
        "Actually make a {topic}. Save it in Word.",
        "Hey Maya, make me a {topic}. Put this in Word.",
        "Please create a {topic}; this needs to be Word.",
        "Could you prepare a {topic}. This should be a Word document.",
        "Make me a {topic} Word document for this project.",
        "Hey, may I create a {topic}? This has to be in Word.",
        "make me a {topic} to be in Word",
    )
    return _expand(templates, "docx")


def _xlsx_cases() -> list[tuple[str, str]]:
    templates = (
        "Hey Maya, make me a {topic} budget tracker.",
        "I need a {topic}. Put it in Excel.",
        "Can you create a {topic} spreadsheet?",
        "Could you make an Excel sheet for {topic}?",
        "Please put together a {topic} workbook.",
        "Hey, may I make me a {topic}? It needs to be in Excel.",
        "um create a {topic}; it should be a spreadsheet.",
        "No wait make a {topic}. Save it as Excel.",
        "Can you can you generate a {topic} xlsx?",
        "Help me create a {topic} spending tracker.",
        "I want a {topic}. This has to be a spreadsheet.",
        "Make me a {topic}. Keep it in Excel.",
    )
    return _expand(templates, "xlsx")


def _pptx_cases() -> list[tuple[str, str]]:
    templates = (
        "Hey Maya, make me a {topic} deck.",
        "I need a {topic}. Put it in PowerPoint.",
        "Can you create a presentation about {topic}?",
        "Could you make slides for {topic}?",
        "Please build a PowerPoint about {topic}.",
        "Hey, may I make me a {topic}? It needs to be a deck.",
        "um create a {topic}; it should be a presentation.",
        "No wait make a {topic}. Save it as PowerPoint.",
        "Can you can you generate a {topic} pptx?",
        "Help me create a {topic} slide deck.",
        "I want a {topic}. This has to be a deck.",
        "Make me a {topic}. Keep it in PowerPoint.",
    )
    return _expand(templates, "pptx")


def _expand(templates: tuple[str, ...], kind: str) -> list[tuple[str, str]]:
    return [(template.format(topic=topic), kind) for topic in TOPICS for template in templates]


if __name__ == "__main__":
    main()
