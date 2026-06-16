from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from xai_voice_work import set_voice_work_phase, voice_work_cancel_requested


_current_db_path: ContextVar[str] = ContextVar("maya_voice_work_db_path", default="")
_current_work_id: ContextVar[str] = ContextVar("maya_voice_work_id", default="")


@contextmanager
def voice_work_context(db_path: str, work_id: str | None):
    db_token = _current_db_path.set(db_path or "")
    work_token = _current_work_id.set(work_id or "")
    try:
        yield
    finally:
        _current_db_path.reset(db_token)
        _current_work_id.reset(work_token)


async def set_current_voice_work_phase(phase: str, detail: str = "") -> bool:
    db_path = _current_db_path.get()
    work_id = _current_work_id.get()
    if not db_path or not work_id:
        return True
    return await set_voice_work_phase(db_path, work_id, phase, detail)


async def current_voice_work_cancel_requested() -> bool:
    db_path = _current_db_path.get()
    work_id = _current_work_id.get()
    if not db_path or not work_id:
        return False
    return await voice_work_cancel_requested(db_path, work_id)


def current_voice_work_db_path() -> str:
    return _current_db_path.get()


def current_voice_work_id() -> str:
    return _current_work_id.get()
