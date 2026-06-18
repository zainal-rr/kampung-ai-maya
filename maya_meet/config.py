from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from maya_core.secret_provider import get_secret


@dataclass(frozen=True)
class RecallConfig:
    api_key: str
    base_url: str
    verification_secret: str
    public_callback_url: str
    output_media_url: str
    output_media_token: str
    bot_name: str = "Maya"
    audio_wake_enabled: bool = False
    public_audio_ws_url: str = ""

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        for name in ("api_key", "verification_secret", "public_callback_url", "output_media_url", "output_media_token"):
            if not getattr(self, name):
                missing.append(name)
        return tuple(missing)

    def ready(self) -> bool:
        return not self.missing_fields()


def recall_config_from_env() -> RecallConfig:
    return RecallConfig(
        api_key=get_secret("RECALL_API_KEY", "") or "",
        base_url=os.getenv("RECALL_BASE_URL", "https://us-west-2.recall.ai/api/v1").rstrip("/"),
        verification_secret=get_secret("RECALL_VERIFICATION_SECRET", "") or "",
        public_callback_url=os.getenv("RECALL_PUBLIC_CALLBACK_URL", "").strip(),
        output_media_url=os.getenv("MAYA_MEET_OUTPUT_MEDIA_URL", "").strip(),
        output_media_token=get_secret("MAYA_MEET_OUTPUT_TOKEN", "") or "",
        bot_name=os.getenv("MAYA_MEET_BOT_NAME", "Maya").strip() or "Maya",
        audio_wake_enabled=os.getenv("MAYA_MEET_AUDIO_WAKE", "0") == "1",
        public_audio_ws_url=os.getenv("RECALL_PUBLIC_AUDIO_WS_URL", "").strip(),
    )


def output_media_url_with_token(config: RecallConfig, *, session_id: str = "") -> str:
    if not config.output_media_url:
        return ""
    parts = urlsplit(config.output_media_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("token", config.output_media_token)
    if session_id:
        query.setdefault("session_id", session_id)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def audio_wake_url(config: RecallConfig, *, session_id: str = "") -> str:
    if config.public_audio_ws_url:
        base = config.public_audio_ws_url
    else:
        if not config.public_callback_url:
            return ""
        parts = urlsplit(config.public_callback_url)
        scheme = "wss" if parts.scheme == "https" else "ws"
        base = urlunsplit((scheme, parts.netloc, "/recall/audio-wake", "", ""))
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("token", config.output_media_token)
    if session_id:
        query.setdefault("session_id", session_id)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/recall/audio-wake", urlencode(query), parts.fragment))
