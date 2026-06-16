"""Species-aware deck palettes.

Every deck species gets a full visual identity within its theme family:
species-tinted backgrounds (hue-shifted near-blacks for dark, tinted creams
for pastel), harmonized panel and card surfaces lifted from that background,
and a species accent system for the accent bar, number cards, timeline
markers, kickers, and callout strips. Text colors are shared across species
and every dark background stays dark (max channel < 80) while every pastel
background stays light (min channel > 200), so contrast holds everywhere.

Deterministic by species: no randomness, replay and golden smokes stay stable.
"technical" and "general" keep the original 12161C / FAF8F4 surfaces and blue
or gold accents, so the base Maya look remains the recognizable default.
"""

from __future__ import annotations

from dataclasses import dataclass

from pptx.dml.color import RGBColor

from maya_documents.deck_species import detect_deck_species
from maya_documents.office_pptx_colors import (
    DARK_ACCENT, DARK_BG, DARK_CARD, DARK_PANEL,
    FOREST, GOLD, PASTEL_BG, PASTEL_CARD, PASTEL_PANEL, SAGE,
)


@dataclass(frozen=True)
class DeckPalette:
    species: str
    accent: RGBColor        # primary accent: numbers, markers, strips
    accent_soft: RGBColor   # outlines and quiet secondary accents
    kicker: RGBColor        # small label text above headlines
    bar: RGBColor           # left edge accent bar
    background: RGBColor    # slide background (species-tinted, same lightness family)
    panel: RGBColor         # large panel fill, lifted from the background
    card: RGBColor          # card fill, lifted further from the background


# Original pastel accent-bar green (kept for themes without a species palette).
_PASTEL_BAR_DEFAULT = RGBColor(24, 92, 58)


# Dark-theme accents (on DARK_BG 12161C; all chosen for >= 4.5:1 contrast).
_DARK_ACCENTS: dict[str, tuple[RGBColor, RGBColor]] = {
    "travel": (RGBColor(255, 179, 102), RGBColor(196, 149, 106)),   # warm amber
    "food": (RGBColor(255, 138, 128), RGBColor(199, 124, 117)),     # coral
    "teaching": (RGBColor(126, 217, 154), RGBColor(110, 168, 126)), # green
    "review": (RGBColor(190, 156, 255), RGBColor(150, 130, 191)),   # violet
    "pitch": (RGBColor(240, 198, 92), RGBColor(186, 158, 90)),      # gold
    "issue": (RGBColor(99, 211, 206), RGBColor(96, 161, 158)),      # teal
    "browser": (RGBColor(255, 158, 187), RGBColor(191, 126, 146)),  # rose
    "proposal": (RGBColor(121, 167, 255), RGBColor(120, 142, 184)), # original blue family
}

# Pastel-theme accents (on PASTEL_BG FAF8F4; deeper tones for light ground).
_PASTEL_ACCENTS: dict[str, tuple[RGBColor, RGBColor]] = {
    "travel": (RGBColor(176, 94, 23), RGBColor(196, 149, 106)),
    "food": (RGBColor(176, 58, 46), RGBColor(199, 124, 117)),
    "teaching": (RGBColor(28, 199, 77), RGBColor(110, 168, 126)),
    "review": (RGBColor(94, 53, 177), RGBColor(150, 130, 191)),
    "pitch": (RGBColor(154, 116, 28), RGBColor(186, 158, 90)),
    "issue": (RGBColor(13, 188, 134), RGBColor(96, 161, 158)),
    "browser": (RGBColor(173, 20, 87), RGBColor(191, 126, 146)),
    "proposal": (RGBColor(16, 88, 57), RGBColor(143, 166, 148)),
}

# Species backgrounds: hue-shifted near-blacks for dark and tinted creams for
# pastel, all in the same lightness family as the originals so the existing
# text colors keep their contrast. (background, panel, card) per species.
_DARK_SURFACES: dict[str, tuple[RGBColor, RGBColor, RGBColor]] = {
    "travel": (RGBColor(26, 21, 16), RGBColor(45, 37, 28), RGBColor(60, 50, 38)),
    "food": (RGBColor(28, 18, 17), RGBColor(48, 32, 30), RGBColor(64, 44, 41)),
    "teaching": (RGBColor(16, 24, 19), RGBColor(28, 42, 33), RGBColor(39, 56, 45)),
    "review": (RGBColor(24, 18, 30), RGBColor(40, 32, 52), RGBColor(54, 44, 70)),
    "pitch": (RGBColor(26, 22, 14), RGBColor(45, 39, 26), RGBColor(61, 53, 37)),
    "issue": (RGBColor(14, 24, 24), RGBColor(26, 42, 42), RGBColor(37, 57, 57)),
    "browser": (RGBColor(26, 17, 21), RGBColor(46, 31, 38), RGBColor(62, 43, 52)),
}

_PASTEL_SURFACES: dict[str, tuple[RGBColor, RGBColor, RGBColor]] = {
    "travel": (RGBColor(250, 245, 235), RGBColor(242, 233, 216), RGBColor(255, 252, 245)),
    "food": (RGBColor(251, 243, 240), RGBColor(246, 228, 222), RGBColor(255, 252, 248)),
    "teaching": (RGBColor(243, 249, 244), RGBColor(226, 242, 229), RGBColor(253, 255, 252)),
    "review": (RGBColor(247, 244, 251), RGBColor(234, 228, 245), RGBColor(254, 252, 255)),
    "pitch": (RGBColor(250, 246, 232), RGBColor(242, 235, 210), RGBColor(255, 253, 246)),
    "issue": (RGBColor(240, 248, 247), RGBColor(223, 240, 238), RGBColor(252, 255, 254)),
    "browser": (RGBColor(250, 243, 246), RGBColor(244, 227, 234), RGBColor(255, 252, 253)),
}

# Layout rhythm offsets: shifts the index-based layout rotation per species so
# two same-length decks of different species do not share an identical layout
# sequence. technical/general keep offset 0 (original rhythm preserved).
_RHYTHM_OFFSETS: dict[str, int] = {
    "travel": 1,
    "food": 2,
    "teaching": 3,
    "review": 1,
    "pitch": 2,
    "issue": 3,
    "browser": 2,
    "proposal": 0,
}


def palette_for(title: str, theme: str) -> DeckPalette:
    species = detect_deck_species(title)
    if theme == "dark":
        background, panel, card = _DARK_SURFACES.get(species, (DARK_BG, DARK_PANEL, DARK_CARD))
        if species in _DARK_ACCENTS:
            accent, soft = _DARK_ACCENTS[species]
            return DeckPalette(species, accent, soft, accent, accent, background, panel, card)
        return DeckPalette(species, DARK_ACCENT, DARK_ACCENT, DARK_ACCENT, DARK_ACCENT, background, panel, card)
    background, panel, card = _PASTEL_SURFACES.get(species, (PASTEL_BG, PASTEL_PANEL, PASTEL_CARD))
    if species in _PASTEL_ACCENTS:
        accent, soft = _PASTEL_ACCENTS[species]
        return DeckPalette(species, accent, soft, accent, accent, background, panel, card)
    return DeckPalette(species, GOLD, SAGE, GOLD, _PASTEL_BAR_DEFAULT, background, panel, card)


def default_palette(theme: str) -> DeckPalette:
    """The original pre-species colors, used when no palette is provided."""
    if theme == "dark":
        return DeckPalette("general", DARK_ACCENT, DARK_ACCENT, DARK_ACCENT, DARK_ACCENT, DARK_BG, DARK_PANEL, DARK_CARD)
    return DeckPalette("general", GOLD, SAGE, GOLD, _PASTEL_BAR_DEFAULT, PASTEL_BG, PASTEL_PANEL, PASTEL_CARD)


def rhythm_offset(species: str) -> int:
    return _RHYTHM_OFFSETS.get(species, 0)


__all__ = ["DeckPalette", "palette_for", "default_palette", "rhythm_offset", "FOREST"]
