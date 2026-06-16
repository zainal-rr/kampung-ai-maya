"""Process-level guard for the Maya engine.

The app controller may run alongside the launchd engine, but only one engine
process should ever initialize channels, hotkeys, Telegram polling, or adapters.
This lock protects the whole runtime, while telegram_poller_lock.py protects the
Telegram getUpdates loop as a second line of defense.
"""

from __future__ import annotations

import fcntl
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from maya_core.repo_paths import repo_root

logger = logging.getLogger(__name__)

_LOCK_DIR = repo_root(__file__) / "logs"


@dataclass
class EngineLock:
    handle: IO[str] | None
    path: str

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
        except OSError:
            pass
        self.handle = None


def acquire_engine_lock(lock_dir: Path | str | None = None) -> EngineLock | None:
    """Return a held engine lock, or None when another engine is active."""
    if os.getenv("MAYA_ENGINE_LOCK", "1") == "0":
        return EngineLock(None, "(lock disabled by MAYA_ENGINE_LOCK=0)")
    directory = Path(lock_dir) if lock_dir else _LOCK_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "maya_engine.lock"
    handle = open(path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        holder = ""
        try:
            handle.seek(0)
            holder = handle.read().strip()
        except OSError:
            pass
        handle.close()
        logger.critical(
            "Maya engine lock at %s is held by pid %s; refusing to start a duplicate engine.",
            path,
            holder or "unknown",
        )
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return EngineLock(handle, str(path))
