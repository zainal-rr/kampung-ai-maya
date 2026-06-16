"""Single-poller lock: exactly one process may run the Telegram getUpdates loop.

Root cause this prevents (live incident 2026-06-10 ~19:30 UTC): two Maya
processes (app controller + engine) polled the same bot token. Telegram
terminates one poller's connection (`telegram.error.Conflict: terminated by
other getUpdates request`), updates get consumed by whichever instance wins
the race, and in-flight handler tasks die mid-turn — visible user messages
with no reply and no turn record.

The lock is an fcntl flock on a file under `logs/` (gitignored). It is held
for the lifetime of the polling process and released automatically by the OS
if the process dies, so a crashed bot never wedges the next start.

`MAYA_TELEGRAM_POLLER_LOCK=0` disables the lock (deterministic tests only).
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
class PollerLock:
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


def acquire_poller_lock(name: str = "telegram", lock_dir: Path | str | None = None) -> PollerLock | None:
    """Returns a held lock, or None when another process already polls."""
    if os.getenv("MAYA_TELEGRAM_POLLER_LOCK", "1") == "0":
        return PollerLock(None, "(lock disabled by MAYA_TELEGRAM_POLLER_LOCK=0)")
    directory = Path(lock_dir) if lock_dir else _LOCK_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}_poller.lock"
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
            "Telegram poller lock at %s is held by pid %s; refusing to start a second getUpdates loop.",
            path,
            holder or "unknown",
        )
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return PollerLock(handle, str(path))
