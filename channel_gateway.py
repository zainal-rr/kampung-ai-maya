from __future__ import annotations

from channel_adapters import adapter_for
from storage import upsert_preference


async def remember_channel_identity(db_path: str, channel_id: str, external_id: str) -> None:
    adapter = adapter_for(channel_id)
    if adapter is None or not external_id:
        return
    await upsert_preference(db_path, f"{channel_id}_chat_id", external_id, source="channel_gateway")


def channel_envelope(channel_id: str, text: str = "", attachments: tuple[str, ...] = ()) -> dict[str, object]:
    adapter = adapter_for(channel_id)
    return adapter.envelope(text=text, attachments=attachments) if adapter else {}
