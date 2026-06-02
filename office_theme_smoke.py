from __future__ import annotations

import tempfile
from pathlib import Path

from openpyxl import load_workbook
from pptx import Presentation

from office_modern_files import choose_pptx_theme, create_pptx, create_xlsx


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-office-theme-") as tmp:
        root = Path(tmp)
        xlsx = create_xlsx(root / "pastel.xlsx", "Pastel Budget", ["Item", "Estimated", "Actual"], [["Food", 20, 18]])
        book = load_workbook(xlsx)
        sheet = book.active
        _require(sheet["A1"].fill.fgColor.rgb == "00EADCF8", "Excel title should use pastel lavender")
        _require(sheet["A3"].fill.fgColor.rgb == "00DDEEF8", "Excel header should use pastel blue")
        _require(sheet["A4"].fill.fgColor.rgb == "00000000", "Excel data cells should stay neutral")

        _require(choose_pptx_theme("cyber security incident response") == "dark", "security decks should use dark theme")
        _require(choose_pptx_theme("Seoul food trip") == "dark", "PowerPoint decks should default to dark theme")
        _require(choose_pptx_theme("Seoul food trip not dark theme") == "pastel", "explicit no-dark request should use pastel theme")
        _require(choose_pptx_theme("Seoul food trip pastel") == "pastel", "explicit pastel request should use pastel theme")

        dark = create_pptx(root / "dark.pptx", "Cyber Security Incident", [("Risk posture", ["Contain the incident."])])
        default_dark = create_pptx(root / "default-dark.pptx", "Seoul Food Trip", [("Food plan", ["Prioritize restaurants."])])
        pastel = create_pptx(root / "pastel.pptx", "Seoul Food Trip not dark theme", [("Food plan", ["Prioritize restaurants."])])
        dark_deck = Presentation(dark)
        default_dark_deck = Presentation(default_dark)
        pastel_deck = Presentation(pastel)
        _require(_background_rgb(dark_deck) == "12161C", "dark PPTX background mismatch")
        _require(_background_rgb(default_dark_deck) == "12161C", "default PPTX background should be dark")
        _require(_background_rgb(pastel_deck) == "FAF8F4", "pastel PPTX background mismatch")
    print("office_theme_smoke: ok")


def _background_rgb(deck: Presentation) -> str:
    color = deck.slides[0].background.fill.fore_color.rgb
    return str(color)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
