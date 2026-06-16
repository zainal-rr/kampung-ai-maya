from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


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
        # Backgrounds are species-tinted within each theme family: technical
        # keeps the base dark navy, food decks get the warm dark / blush cream
        # variants. Dark variants must stay dark; pastel variants stay light.
        _require(_background_rgb(dark_deck) == "12161C", "technical deck should keep the base dark background")
        _require(_background_rgb(default_dark_deck) == "1C1211", "food deck should use the warm dark background")
        _require(_background_rgb(pastel_deck) == "FBF3F0", "pastel food deck should use the blush cream background")
        _require(_max_channel(default_dark_deck) < 80, "species dark background must stay dark")
        _require(_min_channel(pastel_deck) > 200, "species pastel background must stay light")
    print("office_theme_smoke: ok")


def _background_rgb(deck: Presentation) -> str:
    color = deck.slides[0].background.fill.fore_color.rgb
    return str(color)


def _channels(deck: Presentation) -> tuple[int, int, int]:
    rgb = _background_rgb(deck)
    return int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)


def _max_channel(deck: Presentation) -> int:
    return max(_channels(deck))


def _min_channel(deck: Presentation) -> int:
    return min(_channels(deck))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
