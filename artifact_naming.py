from __future__ import annotations

import re
from pathlib import Path

from office_files import safe_slug


DEFAULT_SLUG_LENGTH = 40


def named_artifact_path(folder: Path, topic: str, suffix: str, *, max_slug: int = DEFAULT_SLUG_LENGTH) -> Path:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    base = safe_slug(_filename_topic(topic), max_length=max_slug)
    return versioned_path(folder / f"{base}-v1{suffix}")


def _filename_topic(topic: str) -> str:
    cleaned = " ".join(str(topic).strip().split())
    cleaned = re.sub(r"^(?:a|an|the)\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^(?:of|about|on|for)\s+(?:a|an|the)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"^(?:simple|quick|rough|starter|basic|editable|complete)\s+",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\b(?:please|for me)\b", " ", cleaned, flags=re.I)
    return " ".join(cleaned.split()) or "maya-work"


def versioned_path(path: Path) -> Path:
    if not path.exists():
        return path
    base_stem = re.sub(r"-v\d+$", "", path.stem)
    for version in range(2, 1000):
        candidate = path.with_name(f"{base_stem}-v{version}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find a free versioned filename for {path.name}.")
