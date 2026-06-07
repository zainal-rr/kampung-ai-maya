from __future__ import annotations

from assistant_text import strip_wake_prefix
from document_natural_artifact_parser import artifact_intent_clarification
from document_request_parser import document_request
from voice_transcript_policy import clean_voice_transcript_for_intent


def main() -> None:
    raw = "Hey, may I make me a two days food trip for Seoul? It needs to be in document."
    cleaned = clean_voice_transcript_for_intent(strip_wake_prefix(raw))
    _require(
        cleaned == "make me a two days food trip for Seoul? It needs to be in document.",
        f"unexpected voice cleanup: {cleaned!r}",
    )
    _require(
        document_request(cleaned) is None,
        f"generic document voice transcript should not route to docx: {document_request(cleaned)!r}",
    )
    clarification = artifact_intent_clarification(cleaned)
    _require(
        clarification is not None and "Word doc, Excel sheet, or PowerPoint slides" in clarification,
        f"generic document voice transcript did not ask artifact type: {clarification!r}",
    )
    print("voice_document_transcript_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
