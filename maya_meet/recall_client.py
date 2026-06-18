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


@dataclass(frozen=True)
class RecallBotState:
    status: str
    reason_code: str
    bot_id: str = ""
    raw_status: str = ""
    sub_code: str = ""
    detail: str = ""

    def is_live(self) -> bool:
        return self.status == "live"

    def is_waiting(self) -> bool:
        return self.status == "waiting"

    def is_terminal(self) -> bool:
        return self.status in {"ended", "fatal", "missing"}

    def as_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "bot_id": self.bot_id,
            "raw_status": self.raw_status,
            "sub_code": self.sub_code,
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


def preflight_public_url(url: str, *, timeout: float = 5, accept_statuses: set[int] | None = None) -> RecallJoinResult | None:
    if not url:
        return RecallJoinResult("failed", "public_url_missing")
    request = urllib.request.Request(
        url,
        headers={"Accept": "text/html,application/json"},
        method="GET",
    )
    accepted = accept_statuses or {200}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        return RecallJoinResult("failed", "public_url_unreachable", detail=str(exc))
    if status not in accepted:
        return RecallJoinResult("failed", "public_url_unreachable", detail=f"http_status={status}")
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


def retrieve_recall_bot(config: RecallConfig, bot_id: str, *, timeout: float = 20) -> RecallBotState:
    if not bot_id:
        return RecallBotState("missing", "missing_bot_id")
    if not config.api_key:
        return RecallBotState("failed", "recall_config_missing", bot_id=bot_id, detail="RECALL_API_KEY")
    request = urllib.request.Request(
        config.base_url.rstrip("/") + f"/bot/{bot_id}/",
        headers={
            "Authorization": f"Token {config.api_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return RecallBotState("missing", "recall_bot_not_found", bot_id=bot_id, detail=f"{exc.code}: {exc.reason}")
        return RecallBotState("failed", "recall_retrieve_http_error", bot_id=bot_id, detail=f"{exc.code}: {exc.reason}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return RecallBotState("failed", "recall_retrieve_failed", bot_id=bot_id, detail=str(exc))
    return _bot_state_from_payload(data, bot_id=bot_id)


def leave_recall_bot(config: RecallConfig, bot_id: str, *, timeout: float = 20) -> RecallJoinResult:
    if not bot_id:
        return RecallJoinResult("failed", "missing_bot_id")
    if not config.api_key:
        return RecallJoinResult("failed", "recall_config_missing", bot_id=bot_id, detail="RECALL_API_KEY")
    request = urllib.request.Request(
        config.base_url.rstrip("/") + f"/bot/{bot_id}/leave_call/",
        data=b"{}",
        headers={
            "Authorization": f"Token {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        return RecallJoinResult("failed", "recall_leave_http_error", bot_id=bot_id, detail=f"{exc.code}: {exc.reason}")
    except (urllib.error.URLError, TimeoutError) as exc:
        return RecallJoinResult("failed", "recall_leave_failed", bot_id=bot_id, detail=str(exc))
    if status >= 400:
        return RecallJoinResult("failed", "recall_leave_http_error", bot_id=bot_id, detail=f"http_status={status}")
    return RecallJoinResult("left", "recall_leave_call_requested", bot_id=bot_id)


def _bot_state_from_payload(data: dict[str, Any], *, bot_id: str) -> RecallBotState:
    raw_status, sub_code = _latest_bot_status(data)
    normalized = normalize_recall_bot_status(raw_status)
    reason = f"recall_bot_{normalized}" if normalized else "recall_bot_status_unknown"
    return RecallBotState(
        status=normalized or "unknown",
        reason_code=reason,
        bot_id=str(data.get("id") or data.get("bot_id") or bot_id),
        raw_status=raw_status,
        sub_code=sub_code,
        detail=json.dumps({"status": raw_status, "sub_code": sub_code}, sort_keys=True),
    )


def _latest_bot_status(data: dict[str, Any]) -> tuple[str, str]:
    direct = str(data.get("status") or data.get("state") or "").strip()
    direct_sub = str(data.get("sub_code") or data.get("status_sub_code") or "").strip()
    changes = data.get("status_changes")
    if isinstance(changes, list) and changes:
        latest = changes[-1] if isinstance(changes[-1], dict) else {}
        code = str(latest.get("code") or latest.get("status") or latest.get("state") or direct).strip()
        sub_code = str(latest.get("sub_code") or latest.get("message") or direct_sub).strip()
        return code, sub_code
    return direct, direct_sub


def normalize_recall_bot_status(raw_status: str) -> str:
    status = raw_status.strip().lower().replace("-", "_").replace(" ", "_")
    if status.startswith("bot."):
        status = status.split(".", 1)[1]
    if status in {"in_call", "in_call_recording", "in_call_not_recording", "joined", "recording"}:
        return "live"
    if status in {"in_waiting_room", "waiting_room"}:
        return "waiting"
    if status in {"joining", "joining_call", "joining_recording", "pending"}:
        return "joining"
    if status in {"done", "call_ended", "left_call", "leaving_call", "completed", "bot_left", "left", "ended"}:
        return "ended"
    if status in {"fatal", "error", "failed"}:
        return "fatal"
    return status
