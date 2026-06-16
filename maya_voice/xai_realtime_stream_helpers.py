from __future__ import annotations

import asyncio
import base64


def append_audio_message(audio: bytes) -> dict:
    return {"type": "input_audio_buffer.append", "audio": base64.b64encode(audio).decode("ascii")}


async def put_playback(queue: asyncio.Queue, item) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    await queue.put(item)


def put_latest(queue: asyncio.Queue, item: bytes) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(item)


def event_error(event: dict) -> str:
    error = event.get("error") or {}
    return error.get("message") if isinstance(error, dict) else str(error or event)
