"""Shared read-only store access + lane masking for the Maya UI server.

READ-ONLY BY CONSTRUCTION: every connection opens the SQLite file with
URI ?mode=ro. This module never imports kampung-ai runtime code and never
writes. The identity rule is enforced here: raw engine names are masked to
Maya's team names before anything leaves this process.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

PROTO = 1
DEFAULT_SCHEMA_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.environ.get("MAYA_UI_DB", _REPO_ROOT / "session_history.db"))

# Identity layer: engine names never cross the API (doctrine: one Maya).
# Masks the engine token plus its version/tier qualifiers ONLY — never the
# surrounding descriptive words ("artifact preflight" must survive).
_QUAL = r"(?:\s+(?:[0-9][\w.]*|flash|pro|premium|image|opus|mini|voice(?:-latest)?))*"
_LANE_MASKS = [
    (re.compile(r"\bnano banana(?:\s+(?:2|pro))?\b", re.I), "The Sight"),
    (re.compile(r"\bgemini\b" + _QUAL, re.I), "The Sight"),
    (re.compile(r"\bgpt[\w.\-]*" + _QUAL, re.I), "The Mind"),
    (re.compile(r"\bopenai\b", re.I), "The Mind"),
    (re.compile(r"\bclaude\b" + _QUAL, re.I), "The Steward"),
    (re.compile(r"\bopus\b" + _QUAL, re.I), "The Steward"),
    (re.compile(r"\banthropic\b", re.I), "The Steward"),
    (re.compile(r"\bgrok\b" + _QUAL, re.I), "The Pulse"),
    (re.compile(r"\bara\b", re.I), "The Pulse"),
    (re.compile(r"\bxai\b", re.I), "The Pulse"),
    (re.compile(r"\bcodex\b" + _QUAL, re.I), "The Artisan"),
    (re.compile(r"\bartisan\b", re.I), "The Artisan"),
]


def mask_lanes(text: str | None) -> str | None:
    """Replace any raw engine mention with the masked team name."""
    if not text:
        return text
    out = text
    for pattern, team in _LANE_MASKS:
        out = pattern.sub(team, out)
    # defense in depth: engine fragments inside identifiers (snake_case keys)
    for frag, team in (("gemini", "The Sight"), ("claude", "The Steward"),
                       ("codex", "The Artisan"), ("grok", "The Pulse"),
                       ("openai", "The Mind"), ("anthropic", "The Steward"),
                       ("xai", "The Pulse")):
        out = re.sub(frag, team, out, flags=re.I)
    # cleanup: duplicated team names and article collisions ("the The Steward")
    out = re.sub(r"\b(The (?:Sight|Mind|Steward|Pulse|Artisan))(\s+\1)+", r"\1", out)
    out = re.sub(r"\b(?:the|a|an)\s+(The (?:Sight|Mind|Steward|Pulse|Artisan))", r"\1", out, flags=re.I)
    return out


_KEY_ENGINE = {
    "gemini": "The Sight", "nano": "The Sight", "banana": "The Sight",
    "gpt": "The Mind", "openai": "The Mind",
    "claude": "The Steward", "opus": "The Steward", "anthropic": "The Steward",
    "grok": "The Pulse", "ara": "The Pulse", "xai": "The Pulse",
    "codex": "The Artisan", "artisan": "The Artisan",
}
_KEY_DROP = {"flash", "pro", "premium", "image", "mini", "latest", "2", "3", "31", "35", "55"}


def mask_lane_key(key: str | None) -> str:
    """Prettify a snake_case usage-lane key into 'Team · rest of key'."""
    if not key:
        return "unknown"
    team, rest = None, []
    for part in key.lower().split("_"):
        if part in _KEY_ENGINE:
            team = team or _KEY_ENGINE[part]
        elif part not in _KEY_DROP and part:
            rest.append(part)
    label = " ".join(rest)
    if team:
        return f"{team} · {label}" if label else team
    return mask_lanes(key) or key


def connect_ro() -> sqlite3.Connection:
    """Open the store strictly read-only. Raises if the file is missing."""
    if not DB_PATH.exists():
        raise FileNotFoundError(str(DB_PATH))
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2.0)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    except sqlite3.Error:
        return False
    return column in cols


def schema_version_of(row: sqlite3.Row, available: bool) -> int:
    """Echo the row's schema_version when the column exists; default otherwise.

    The ALTER TABLE adding schema_version is pending in the kampung-ai repo and
    is deliberately NOT applied by this read-only server.
    """
    if available:
        try:
            value = row["schema_version"]
            if value is not None:
                return int(value)
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    return DEFAULT_SCHEMA_VERSION
