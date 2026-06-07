from __future__ import annotations

from assistant_text import strip_wake_prefix
from document_natural_artifact_parser import artifact_intent_clarification
from document_request_parser import document_request


POSITIVE_CASES = (
    ("Could you write a router setup guide in Word?", ("docx", "router setup guide", False)),
    ("um Could you write a router setup guide in Word?", ("docx", "router setup guide", False)),
    ("Please put together a proposal Word document for Kampung AI quality.", ("docx", "proposal for Kampung AI quality", False)),
    ("I want you to make a monthly spending tracker.", ("xlsx", "monthly spending tracker", False)),
    ("Can you create a food budget tracker for Seoul?", ("xlsx", "food for Seoul budget tracker", False)),
    ("Could you make an Excel sheet for Seoul food expenses?", ("xlsx", "Seoul food expenses", False)),
    ("Please build a PowerPoint about Kampung AI roadmap.", ("pptx", "Kampung AI roadmap", False)),
    ("Can you make me a Seoul food trip deck?", ("pptx", "Seoul food trip deck", False)),
    ("Need a presentation for router migration plan.", ("pptx", "router migration plan", False)),
    ("Help me create a markdown note about office priorities.", ("md", "office priorities", False)),
    ("Can you generate an HTML file for a travel checklist?", ("html", "travel checklist", False)),
    ("make me a Seoul food trip. It should be in Word.", ("docx", "Seoul food trip", False)),
    ("okay wait make me a Seoul food trip. It should be in Word.", ("docx", "Seoul food trip", False)),
    ("I need a two day Seoul food trip. Put it in Word.", ("docx", "two day Seoul food trip", False)),
    ("create a Seoul food budget. It needs to be in Excel.", ("xlsx", "Seoul food budget", False)),
    ("make a Seoul food trip. It has to be a deck.", ("pptx", "Seoul food trip deck", False)),
)

NEGATIVE_CASES = (
    "send me the last document",
    "open the latest deck",
    "what is a document",
    "review this document",
    "where is the spreadsheet",
)


def main() -> None:
    for text, expected in POSITIVE_CASES:
        cleaned = strip_wake_prefix(text)
        result = document_request(cleaned)
        _require(result == expected, f"{text!r} parsed as {result!r}, expected {expected!r}")
    for text in NEGATIVE_CASES:
        result = document_request(text)
        _require(result is None, f"{text!r} should not create an artifact, got {result!r}")
    clarification = artifact_intent_clarification("A Tokyo food cost sheet.")
    _require(clarification is not None and "Do you want me to create" in clarification, "artifact fragment should ask for confirmation")
    generic_doc = artifact_intent_clarification("I need a Seoul food trip document.")
    _require(
        generic_doc is not None and "Word doc, Excel sheet, or PowerPoint slides" in generic_doc,
        "generic document should ask for artifact type",
    )
    generic_voice_doc = artifact_intent_clarification("Hey Maya, can you make me a food trip document to Seoul for two days?")
    _require(
        generic_voice_doc is not None and "Word doc, Excel sheet, or PowerPoint slides" in generic_voice_doc,
        "voice generic document should ask for artifact type",
    )
    _require(artifact_intent_clarification("send me the last document") is None, "last document command should not be artifact clarification")
    print("document_natural_artifact_parser_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
