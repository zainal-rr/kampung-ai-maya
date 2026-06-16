from __future__ import annotations

import re


def _plain(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip(" :")


def _complete(text: str) -> str:
    clean = " ".join(str(text).split()).strip(" ,;:-")
    if not clean:
        return ""
    return clean if clean.endswith((".", "?", "!", ")")) else clean + "."
