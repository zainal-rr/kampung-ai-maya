from __future__ import annotations

from document_request_parser import document_request


CASES = (
    ("make me a Word document for a 2-day Seoul food trip", ("docx", "2-day Seoul food trip", False)),
    ("make me a 2-day Seoul food trip Word document", ("docx", "2-day Seoul food trip", False)),
    ("make me a Seoul food trip doc", ("docx", "Seoul food trip", False)),
    ("make router setup guide in Word", ("docx", "router setup guide", False)),
    ("write proposal doc for Kampung AI quality", ("docx", "proposal for Kampung AI quality", False)),
    ("make me a Word document for this project about launch notes", ("docx", "launch notes", True)),
    ("make me a Seoul food trip budget tracker in Excel", ("xlsx", "Seoul food trip budget tracker", False)),
    ("make me a router setup comparison in Excel", ("xlsx", "router setup comparison", False)),
    ("make me a Seoul food trip deck in PowerPoint", ("pptx", "Seoul food trip deck", False)),
)


def main() -> None:
    for text, expected in CASES:
        result = document_request(text)
        _require(result == expected, f"{text!r} parsed as {result!r}, expected {expected!r}")
    print("document_request_parser_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
