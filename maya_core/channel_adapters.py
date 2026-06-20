from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChannelAdapter:
    channel_id: str
    visible_name: str
    can_send_text: bool
    can_send_files: bool
    can_speak: bool
    can_show_local_app_or_screen: bool
    privacy_level: str
    delivery_limits: dict[str, str] = field(default_factory=dict)

    def envelope(self, text: str = "", event: str = "", attachments: tuple[str, ...] = ()) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "visible_name": self.visible_name,
            "text": text,
            "event": event,
            "attachments": list(attachments),
            "privacy_level": self.privacy_level,
        }


TELEGRAM_ADAPTER = ChannelAdapter(
    "telegram",
    "Telegram",
    True,
    True,
    True,
    False,
    "personal_remote",
    {"text_limit": "split long messages", "files": "generated artifacts only"},
)
IMAC_VOICE_ADAPTER = ChannelAdapter(
    "imac",
    "iMac voice",
    True,
    False,
    True,
    True,
    "personal_local",
    {"spoken_reply": "short by default"},
)
OMI_ADAPTER = ChannelAdapter(
    "omi",
    "Omi transcript",
    False,
    False,
    False,
    False,
    "ambient_low_priority",
    {"mode": "transcript ingestion only"},
)
MUDRA_ADAPTER = ChannelAdapter(
    "mudra",
    "Mudra event",
    False,
    False,
    False,
    False,
    "hardware_event",
    {"mode": "event recording only"},
)
FUTURE_MESSAGE_ADAPTER = ChannelAdapter(
    "future_message",
    "Future message adapter",
    True,
    True,
    False,
    False,
    "external_pending_review",
    {"status": "placeholder only"},
)


def all_adapters() -> tuple[ChannelAdapter, ...]:
    return (TELEGRAM_ADAPTER, IMAC_VOICE_ADAPTER, OMI_ADAPTER, MUDRA_ADAPTER, FUTURE_MESSAGE_ADAPTER)


def adapter_for(channel_id: str) -> ChannelAdapter | None:
    for adapter in all_adapters():
        if adapter.channel_id == channel_id:
            return adapter
    return None
