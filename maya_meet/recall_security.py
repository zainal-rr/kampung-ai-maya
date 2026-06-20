from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Mapping


class RecallSignatureError(ValueError):
    pass


def verify_recall_signature(
    *,
    secret: str,
    headers: Mapping[str, str],
    payload: str | bytes | None,
    max_age_seconds: int = 300,
    now: float | None = None,
) -> None:
    clean_secret = str(secret or "")
    if not clean_secret.startswith("whsec_"):
        raise RecallSignatureError("missing_or_invalid_verification_secret")
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    message_id = lowered.get("webhook-id") or lowered.get("svix-id")
    timestamp = lowered.get("webhook-timestamp") or lowered.get("svix-timestamp")
    signature_header = lowered.get("webhook-signature") or lowered.get("svix-signature")
    if not message_id or not timestamp or not signature_header:
        raise RecallSignatureError("missing_signature_headers")
    try:
        age = abs((now if now is not None else time.time()) - int(timestamp))
    except ValueError as exc:
        raise RecallSignatureError("invalid_signature_timestamp") from exc
    if max_age_seconds > 0 and age > max_age_seconds:
        raise RecallSignatureError("signature_timestamp_stale")

    payload_text = _payload_text(payload)
    key = base64.b64decode(clean_secret.removeprefix("whsec_"))
    signed = f"{message_id}.{timestamp}.{payload_text}".encode("utf-8")
    expected = hmac.new(key, signed, hashlib.sha256).digest()
    for versioned in signature_header.split(" "):
        try:
            version, encoded = versioned.split(",", 1)
        except ValueError:
            continue
        if version != "v1":
            continue
        try:
            provided = base64.b64decode(encoded)
        except ValueError:
            continue
        if len(provided) == len(expected) and hmac.compare_digest(provided, expected):
            return
    raise RecallSignatureError("no_matching_signature")


def recall_test_signature(secret: str, *, message_id: str, timestamp: str, payload: str | bytes | None) -> str:
    key = base64.b64decode(str(secret).removeprefix("whsec_"))
    signed = f"{message_id}.{timestamp}.{_payload_text(payload)}".encode("utf-8")
    return "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")


def _payload_text(payload: str | bytes | None) -> str:
    if payload is None:
        return ""
    if isinstance(payload, bytes):
        return payload.decode("utf-8")
    return str(payload)
