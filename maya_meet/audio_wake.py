from __future__ import annotations

import base64
import json
import os
import pickle
import re
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from scipy.io.wavfile import write as write_wav

DEFAULT_MODEL_PATH = Path.home() / "Desktop/Maya/artifacts/wakeword_models/maya_wake_scorer.pkl"


class AudioWakeScorer(Protocol):
    def score(self, audio: np.ndarray) -> float:
        ...


@dataclass(frozen=True)
class AudioWakeMatch:
    matched: bool
    confidence: float = 0.0
    delay_seconds: float = 0.0
    reason_code: str = "audio_wake_not_matched"


class RecallAudioWakeState:
    def __init__(
        self,
        *,
        scorer: AudioWakeScorer | None = None,
        enabled: bool = False,
        threshold: float | None = None,
        window_seconds: float | None = None,
        score_every_seconds: float | None = None,
        match_before_seconds: float | None = None,
        match_after_seconds: float | None = None,
    ):
        self.enabled = enabled
        self.scorer = scorer or LocalWakeAudioScorer()
        self.threshold = threshold if threshold is not None else float(os.getenv("MAYA_MEET_AUDIO_WAKE_THRESHOLD", "0.70"))
        self.window_seconds = window_seconds if window_seconds is not None else float(os.getenv("MAYA_MEET_AUDIO_WAKE_WINDOW_SECONDS", "4.0"))
        self.score_every_seconds = (
            score_every_seconds if score_every_seconds is not None else float(os.getenv("MAYA_MEET_AUDIO_WAKE_SCORE_EVERY", "0.5"))
        )
        self.match_before_seconds = (
            match_before_seconds if match_before_seconds is not None else float(os.getenv("MAYA_MEET_AUDIO_WAKE_MATCH_BEFORE_SECONDS", "1.0"))
        )
        self.match_after_seconds = (
            match_after_seconds if match_after_seconds is not None else float(os.getenv("MAYA_MEET_AUDIO_WAKE_MATCH_AFTER_SECONDS", "8.0"))
        )
        self._audio = deque(maxlen=max(16000, int(16000 * self.window_seconds)))
        self._last_score_at = 0.0
        self._last_wake_at = 0.0
        self._last_wake_score = 0.0
        self._suppress_until = 0.0
        self._playback_active = False

    @classmethod
    def from_env(cls) -> RecallAudioWakeState:
        return cls(enabled=os.getenv("MAYA_MEET_AUDIO_WAKE", "0") == "1")

    def suppress_for(self, seconds: float, *, now: float | None = None) -> None:
        base = now if now is not None else time.time()
        self._suppress_until = max(self._suppress_until, base + max(0.0, seconds))

    def begin_playback_suppression(self, *, max_seconds: float = 120.0, now: float | None = None) -> None:
        self.clear_pending_wake()
        self._playback_active = True
        base = now if now is not None else time.time()
        self._suppress_until = base + max(0.0, max_seconds)

    def end_playback_suppression(self, *, tail_seconds: float = 2.0, now: float | None = None) -> None:
        self.clear_pending_wake()
        self._playback_active = False
        base = now if now is not None else time.time()
        self._suppress_until = base + max(0.0, tail_seconds)

    def clear_pending_wake(self) -> None:
        self._last_wake_at = 0.0
        self._last_wake_score = 0.0

    def ingest_pcm_bytes(self, audio: bytes, *, audio_timestamp: float | None = None, now: float | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "ignored", "reason_code": "audio_wake_disabled"}
        current = now if now is not None else time.time()
        if current < self._suppress_until:
            return {"status": "ignored", "reason_code": "audio_wake_suppressed"}
        if not audio:
            return {"status": "ignored", "reason_code": "audio_wake_empty"}
        samples = np.frombuffer(audio, dtype="<i2").astype(np.int16, copy=False)
        self._audio.extend(int(sample) for sample in samples)
        if len(self._audio) < int(16000 * min(1.0, self.window_seconds)):
            return {"status": "ignored", "reason_code": "audio_wake_buffering"}
        if current - self._last_score_at < self.score_every_seconds:
            return {"status": "ignored", "reason_code": "audio_wake_score_throttled"}
        self._last_score_at = current
        window = np.asarray(list(self._audio), dtype=np.int16)
        score = float(self.scorer.score(window))
        if score < self.threshold:
            return {"status": "ignored", "reason_code": "audio_wake_below_threshold", "score": f"{score:.3f}"}
        self._last_wake_at = audio_timestamp if audio_timestamp is not None else current
        self._last_wake_score = score
        return {"status": "accepted", "reason_code": "audio_wake_detected", "score": f"{score:.3f}"}

    def match_transcript(self, *, transcript_timestamp: float | None = None, now: float | None = None) -> AudioWakeMatch:
        if not self.enabled or not self._last_wake_at:
            return AudioWakeMatch(False)
        current = transcript_timestamp if transcript_timestamp is not None else (now if now is not None else time.time())
        delay = current - self._last_wake_at
        if -self.match_before_seconds <= delay <= self.match_after_seconds:
            score = self._last_wake_score
            self._last_wake_at = 0.0
            self._last_wake_score = 0.0
            return AudioWakeMatch(True, score, delay, "audio_wake_matched_transcript")
        if delay > self.match_after_seconds:
            self._last_wake_at = 0.0
            self._last_wake_score = 0.0
        return AudioWakeMatch(False, self._last_wake_score, delay, "audio_wake_not_matched")


class LocalWakeAudioScorer:
    def __init__(self, *, model_path: Path | None = None):
        self.model_path = model_path or Path(os.getenv("LOCAL_WAKE_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
        self._scorer = None
        self._extractor = None

    def score(self, audio: np.ndarray) -> float:
        self._load()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "meet_wake_candidate.wav"
            write_wav(path, 16000, audio.astype(np.int16, copy=False))
            from maya_core.wakeword_sample_scorer import clip_features

            features = clip_features(path, self._extractor)
        return float(self._scorer.predict_proba(features)[0][1])

    def _load(self) -> None:
        if self._scorer is None:
            with self.model_path.open("rb") as handle:
                self._scorer = pickle.load(handle)
        if self._extractor is None:
            from openwakeword.utils import AudioFeatures

            self._extractor = AudioFeatures(inference_framework="onnx", ncpu=1)


def audio_bytes_from_recall_message(message: str | bytes | dict[str, Any]) -> bytes:
    if isinstance(message, bytes):
        return message
    payload = _json_object(message)
    if not payload:
        return b""
    encoded = _find_base64_audio(payload)
    if not encoded:
        return b""
    try:
        return base64.b64decode(encoded, validate=False)
    except Exception:
        return b""


def timestamp_from_recall_payload(payload: dict[str, Any]) -> float | None:
    for key in ("timestamp", "created_at", "start_timestamp", "start_time", "audio_timestamp"):
        value = payload.get(key)
        parsed = _parse_timestamp(value)
        if parsed is not None:
            return parsed
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if data:
        return timestamp_from_recall_payload(data)
    return None


def _json_object(message: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(message, dict):
        return message
    if isinstance(message, bytes):
        try:
            message = message.decode("utf-8")
        except UnicodeDecodeError:
            return {}
    try:
        value = json.loads(message)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _find_base64_audio(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("audio", "buffer", "bytes", "payload"):
            item = value.get(key)
            if isinstance(item, str) and _looks_like_base64(item):
                return item
        data = value.get("data")
        if isinstance(data, str) and _looks_like_base64(data):
            return data
        for item in value.values():
            found = _find_base64_audio(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_base64_audio(item)
            if found:
                return found
    return ""


def _looks_like_base64(value: str) -> bool:
    cleaned = value.strip()
    return len(cleaned) >= 16 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", cleaned) is not None


def _parse_timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 1000 if number > 10_000_000_000 else number
    if isinstance(value, str) and value.strip():
        try:
            return _parse_timestamp(float(value.strip()))
        except ValueError:
            return None
    return None
