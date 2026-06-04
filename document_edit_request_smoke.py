from __future__ import annotations

from document_actions_word_helpers import _document_edit_request


def main() -> None:
    cases = {
        "Turn this into meeting minutes: discussed Q3 hiring, budget freeze, and next Friday review.": None,
        "make that into 3 bullets": None,
        "update that document to include budget notes": ("include budget notes", False),
        "turn this document into a shorter version": ("shorter version", False),
    }
    for text, expected in cases.items():
        result = _document_edit_request(text)
        if result != expected:
            raise AssertionError(f"{text!r} parsed as {result!r}, expected {expected!r}")
    print("document_edit_request_smoke: ok")


if __name__ == "__main__":
    main()
