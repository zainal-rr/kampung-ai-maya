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


CASES = (
    ("make me a Word document for a 2-day Seoul food trip", ("docx", "2-day Seoul food trip", False)),
    ("make me a 2-day Seoul food trip Word document", ("docx", "2-day Seoul food trip", False)),
    ("make me a Seoul food trip doc", ("docx", "Seoul food trip", False)),
    ("make router setup guide in Word", ("docx", "router setup guide", False)),
    ("um make router setup guide in Word", ("docx", "router setup guide", False)),
    ("okay wait make router setup guide in Word", ("docx", "router setup guide", False)),
    ("write proposal doc for Kampung AI quality", ("docx", "proposal for Kampung AI quality", False)),
    ("make me a Word document for this project about launch notes", ("docx", "launch notes", True)),
    ("make me a Tokyo itinerary trip for 4 days with 2 people", ("docx", "Tokyo itinerary trip for 4 days with 2 people", False)),
    ("make me a router config", ("docx", "router config", False)),
    ("prepare a technical troubleshooting guide", ("docx", "technical troubleshooting guide", False)),
    ("draft a Kampung AI quality proposal", ("docx", "Kampung AI quality proposal", False)),
    ("make me a Seoul food trip budget tracker in Excel", ("xlsx", "Seoul food trip budget tracker", False)),
    ("um make me a Seoul food trip budget tracker in Excel", ("xlsx", "Seoul food trip budget tracker", False)),
    ("make me a Seoul food trip budget tracker", ("xlsx", "Seoul food trip budget tracker", False)),
    ("make me a Seoul food trip spreadsheet", ("xlsx", "Seoul food trip", False)),
    ("make me a Seoul food trip Excel budget tracker", ("xlsx", "Seoul food trip budget tracker", False)),
    ("create an Excel sheet for Tokyo Mills two days two pack?", ("xlsx", "sheet for Tokyo Mills two days two pack", False)),
    ("In a Tokyo dining cost tracker, today's number of people is 2.", ("xlsx", "Tokyo dining cost tracker number of people is 2", False)),
    ("Put my Tokyo restaurant spending plan in Excel for 2 days and 2 adult.", ("xlsx", "Tokyo restaurant spending plan for 2 days and 2 adult", False)),
    ("make me a router setup comparison in Excel", ("xlsx", "router setup comparison", False)),
    ("make me a Seoul food trip deck in PowerPoint", ("pptx", "Seoul food trip deck", False)),
    ("make me a Seoul food trip deck", ("pptx", "Seoul food trip deck", False)),
    ("make me a Seoul food trip presentation", ("pptx", "Seoul food trip presentation", False)),
    ("make me a Seoul food trip PowerPoint deck", ("pptx", "Seoul food trip deck", False)),
    ("make me a small PowerPoint deck about weekly office priorities", ("pptx", "weekly office priorities", False)),
)


def main() -> None:
    for text, expected in CASES:
        result = document_request(text)
        _require(result == expected, f"{text!r} parsed as {result!r}, expected {expected!r}")
    for text in (
        "make me a Seoul food trip document.",
        "make me a food trip document to Seoul for two days.",
    ):
        _require(document_request(text) is None, f"{text!r} should ask for artifact type, not default to docx")
    voice_text = strip_wake_prefix("Hey Maya, make me a Seoul food trip document for two days in Seoul.")
    _require(
        document_request(voice_text) is None,
        "voice wake-prefix generic document request should ask for artifact type",
    )
    print("document_request_parser_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
