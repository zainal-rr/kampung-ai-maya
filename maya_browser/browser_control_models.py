from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserPage:
    title: str
    url: str
    text: str
    text_hash: str = ""
    modal_state: str = ""
    untrusted_influence: bool = False
    injection_detected: bool = False
    untrusted_source: str = "browser"
    untrusted_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class BrowserElement:
    label: str
    kind: str
