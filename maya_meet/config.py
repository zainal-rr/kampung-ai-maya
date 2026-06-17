from __future__ import annotations

import os
from dataclasses import dataclass

from maya_core.secret_provider import get_secret


@dataclass(frozen=True)
class RecallConfig:
    api_key: str
    base_url: str
    verification_secret: str
    public_callback_url: str
    output_media_url: str
    bot_name: str = "Maya"

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        for name in ("api_key", "verification_secret", "public_callback_url", "output_media_url"):
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
        bot_name=os.getenv("MAYA_MEET_BOT_NAME", "Maya").strip() or "Maya",
    )
