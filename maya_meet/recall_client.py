from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from maya_meet.config import RecallConfig


@dataclass(frozen=True)
class RecallJoinResult:
    status: str
    reason_code: str
    bot_id: str = ""
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "bot_id": self.bot_id,
            "detail": self.detail,
        }


def create_bot_payload(config: RecallConfig, meeting_url: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "meeting_url": meeting_url,
        "bot_name": config.bot_name,
        "metadata": {"maya_mode": "meet_m1_passive"},
    }
    if config.output_media_url:
        payload["output_media"] = {"camera": {"kind": "webpage", "config": {"url": config.output_media_url}}}
    return payload


def create_recall_bot(config: RecallConfig, meeting_url: str, *, timeout: float = 20) -> RecallJoinResult:
    missing = config.missing_fields()
    if missing:
        return RecallJoinResult("failed", "recall_config_missing", detail=", ".join(missing))
    request = urllib.request.Request(
        config.base_url + "/bot/",
        data=json.dumps(create_bot_payload(config, meeting_url)).encode("utf-8"),
        headers={
            "Authorization": f"Token {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return RecallJoinResult("failed", "recall_join_http_error", detail=f"{exc.code}: {exc.reason}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return RecallJoinResult("failed", "recall_join_failed", detail=str(exc))
    bot_id = str(data.get("id") or data.get("bot_id") or "")
    if not bot_id:
        return RecallJoinResult("failed", "recall_join_missing_bot_id", detail=json.dumps(data, sort_keys=True)[:500])
    return RecallJoinResult("joined", "recall_bot_created", bot_id=bot_id)
