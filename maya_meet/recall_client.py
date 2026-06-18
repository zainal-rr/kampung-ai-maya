from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from maya_meet.config import RecallConfig, audio_wake_url, output_media_url_with_token


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


def create_bot_payload(config: RecallConfig, meeting_url: str, *, session_id: str = "") -> dict[str, Any]:
    metadata = {"maya_mode": "meet_m1_passive"}
    if session_id:
        metadata["maya_session_id"] = session_id
    payload: dict[str, Any] = {
        "meeting_url": meeting_url,
        "bot_name": config.bot_name,
        "metadata": metadata,
        "recording_config": {
            "transcript": {
                "provider": {
                    "recallai_streaming": {
                        "mode": "prioritize_low_latency",
                        "language_code": "en",
                    },
                },
            },
            "realtime_endpoints": [
                {
                    "type": "webhook",
                    "url": config.public_callback_url,
                    "events": ["transcript.data"],
                }
            ],
        },
    }
    if config.output_media_url:
        payload["output_media"] = {"camera": {"kind": "webpage", "config": {"url": output_media_url_with_token(config, session_id=session_id)}}}
    if config.audio_wake_enabled:
        payload["recording_config"]["audio_mixed_raw"] = {}
        payload["recording_config"]["realtime_endpoints"].append(
            {
                "type": "websocket",
                "url": audio_wake_url(config, session_id=session_id),
                "events": ["audio_mixed_raw.data"],
            }
        )
    return payload


def preflight_output_media(config: RecallConfig, *, session_id: str = "", timeout: float = 5) -> RecallJoinResult | None:
    request = urllib.request.Request(
        output_media_url_with_token(config, session_id=session_id),
        headers={"Accept": "text/html,application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        return RecallJoinResult("failed", "output_media_unreachable", detail=str(exc))
    if status >= 400:
        return RecallJoinResult("failed", "output_media_unreachable", detail=f"http_status={status}")
    return None


def create_recall_bot(
    config: RecallConfig,
    meeting_url: str,
    *,
    session_id: str = "",
    timeout: float = 20,
    preflight_output: bool = False,
) -> RecallJoinResult:
    missing = config.missing_fields()
    if missing:
        return RecallJoinResult("failed", "recall_config_missing", detail=", ".join(missing))
    if preflight_output:
        output_failure = preflight_output_media(config, session_id=session_id)
        if output_failure is not None:
            return output_failure
    request = urllib.request.Request(
        config.base_url + "/bot/",
        data=json.dumps(create_bot_payload(config, meeting_url, session_id=session_id)).encode("utf-8"),
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
    return RecallJoinResult("created", "recall_bot_created", bot_id=bot_id)
