from __future__ import annotations

import asyncio
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from maya_core.execution_broker_read_policy import personal_data_read_denies
from maya_core.repo_paths import repo_root


ALLOWED_AUDIO_SUFFIXES = frozenset({".mp3", ".m4a", ".aiff", ".wav"})
GENERATED_AUDIO_ROOT = (repo_root(__file__) / "logs").resolve()


@dataclass(frozen=True)
class QueuedUtterance:
    utterance_id: str
    file_path: Path
    session_id: str
    created_at: float
    expires_at: float
    delivered: bool = False
    preview: str = ""

    def as_dict(self, *, token: str) -> dict[str, Any]:
        return {
            "id": self.utterance_id,
            "audio_url": f"/meet/output/audio/{self.utterance_id}?token={token}&session_id={self.session_id}",
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "preview": self.preview,
        }


class MeetOutputQueue:
    def __init__(self, *, root: Path | None = None, token: str, ttl_seconds: int = 300):
        if not token:
            raise ValueError("Meet output token is required")
        self.root = (root or Path.home() / "Library" / "Caches" / "Kampung AI" / "meet_output").expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.token = token
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, QueuedUtterance] = {}
        self._lock = asyncio.Lock()

    async def queue_audio(self, source_path: Path, *, preview: str = "", session_id: str = "") -> QueuedUtterance:
        source = source_path.expanduser().resolve()
        if _is_protected_path(source) and not _is_maya_generated_audio(source):
            raise ValueError("protected_audio_source")
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(str(source))
        suffix = source.suffix.lower()
        if suffix not in ALLOWED_AUDIO_SUFFIXES:
            raise ValueError("unsupported_audio_type")
        utterance_id = uuid.uuid4().hex
        target = (self.root / f"{utterance_id}{suffix}").resolve()
        if not _is_under(target, self.root):
            raise ValueError("output_path_escape")
        await asyncio.to_thread(shutil.copyfile, source, target)
        now = time.time()
        item = QueuedUtterance(
            utterance_id=utterance_id,
            file_path=target,
            session_id=_safe_session_id(session_id),
            created_at=now,
            expires_at=now + self.ttl_seconds,
            preview=" ".join(preview.split())[:160],
        )
        async with self._lock:
            self._items[utterance_id] = item
            self._prune_locked(now)
        return item

    async def next_utterance(self, token: str, *, session_id: str = "") -> dict[str, Any] | None:
        clean_session_id = _safe_session_id(session_id)
        if token != self.token or not clean_session_id:
            return None
        now = time.time()
        async with self._lock:
            self._prune_locked(now)
            for item in list(self._items.values()):
                if item.session_id == clean_session_id and not item.delivered:
                    delivered = QueuedUtterance(
                        utterance_id=item.utterance_id,
                        file_path=item.file_path,
                        session_id=item.session_id,
                        created_at=item.created_at,
                        expires_at=item.expires_at,
                        delivered=True,
                        preview=item.preview,
                    )
                    self._items[item.utterance_id] = delivered
                    return delivered.as_dict(token=token)
        return None

    async def audio_path(self, utterance_id: str, token: str, *, session_id: str = "") -> Path | None:
        clean_session_id = _safe_session_id(session_id)
        if token != self.token or not _safe_id(utterance_id) or not clean_session_id:
            return None
        now = time.time()
        async with self._lock:
            self._prune_locked(now)
            item = self._items.get(utterance_id)
            if item is None:
                return None
            if item.session_id != clean_session_id:
                return None
            path = item.file_path.resolve()
            if not _is_under(path, self.root) or _is_protected_path(path) or not path.exists():
                return None
            return path

    def _prune_locked(self, now: float) -> None:
        expired = [key for key, item in self._items.items() if item.expires_at < now]
        for key in expired:
            item = self._items.pop(key)
            try:
                item.file_path.unlink()
            except FileNotFoundError:
                pass


def _safe_id(value: str) -> bool:
    return len(value) == 32 and all(char in "0123456789abcdef" for char in value)


def _safe_session_id(value: str) -> str:
    text = str(value or "").strip()
    if 1 <= len(text) <= 120 and all(char.isalnum() or char in {"_", "-"} for char in text):
        return text
    return ""


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_protected_path(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    for denied in personal_data_read_denies(()):
        denied_path = denied.expanduser().resolve()
        if resolved == denied_path or _is_under(resolved, denied_path):
            return True
    return False


def _is_maya_generated_audio(path: Path) -> bool:
    return (
        path.name.startswith("speech_")
        and path.suffix.lower() in ALLOWED_AUDIO_SUFFIXES
        and _is_under(path, GENERATED_AUDIO_ROOT)
    )
