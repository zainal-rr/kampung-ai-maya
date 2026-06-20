from __future__ import annotations

import asyncio
import os
import pickle
import tempfile
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from openwakeword.utils import AudioFeatures
from scipy.io.wavfile import write as write_wav

from maya_core.wakeword_sample_scorer import clip_features


DEFAULT_MODEL_PATH = Path.home() / "Desktop/Maya/artifacts/wakeword_models/maya_wake_scorer.pkl"


class LocalWakeScorerTranscriptSource:
    def __init__(
        self,
        device_name: str | None = None,
        model_path: Path | None = None,
        threshold: float | None = None,
        listen_seconds: int | None = None,
        ready_delay: float | None = None,
        rest_seconds: float | None = None,
        score_seconds: float | None = None,
        score_every: float | None = None,
        max_wait_seconds: int | None = None,
    ):
        self.device_name = device_name or os.getenv("LOCAL_WAKE_AUDIO_INPUT_NAME", "Zainal’s Headphone")
        self.model_path = model_path or Path(os.getenv("LOCAL_WAKE_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
        self.threshold = threshold if threshold is not None else float(os.getenv("LOCAL_WAKE_THRESHOLD", "0.7"))
        self.listen_seconds = listen_seconds if listen_seconds is not None else int(os.getenv("LOCAL_WAKE_LISTEN_SECONDS", "4"))
        self.ready_delay = ready_delay if ready_delay is not None else float(os.getenv("LOCAL_WAKE_READY_DELAY", "0"))
        self.rest_seconds = rest_seconds if rest_seconds is not None else float(os.getenv("LOCAL_WAKE_REST_SECONDS", "1.5"))
        self.score_seconds = score_seconds if score_seconds is not None else float(os.getenv("LOCAL_WAKE_SCORE_SECONDS", "4"))
        self.score_every = score_every if score_every is not None else float(os.getenv("LOCAL_WAKE_SCORE_EVERY", "0.5"))
        self.max_wait_seconds = max_wait_seconds if max_wait_seconds is not None else int(os.getenv("LOCAL_WAKE_MAX_WAIT_SECONDS", "60"))
        self._scorer = None
        self._extractor = None

    async def listen(self) -> str:
        return await asyncio.to_thread(self._listen_sync)

    def _listen_sync(self) -> str:
        if self.ready_delay > 0:
            time.sleep(self.ready_delay)
        device = _input_index(self.device_name)
        deadline = time.time() + self.max_wait_seconds
        self._load()
        while time.time() < deadline:
            audio = _record_audio(device, self.listen_seconds)
            score, candidate = self._best_score(audio)
            if os.getenv("LOCAL_WAKE_DEBUG", "0") == "1":
                print(f"local-wake> score={score:.3f}")
            if score >= self.threshold:
                _save_candidate(candidate, score)
                return "Maya"
            time.sleep(self.rest_seconds)
        return ""

    def _load(self) -> None:
        if self._scorer is None:
            with self.model_path.open("rb") as handle:
                self._scorer = pickle.load(handle)
        if self._extractor is None:
            self._extractor = AudioFeatures(inference_framework="onnx", ncpu=1)

    def _best_score(self, full_audio: np.ndarray) -> tuple[float, np.ndarray]:
        step = max(1, int(16000 * self.score_every))
        window = max(1, int(16000 * self.score_seconds))
        best_score = 0.0
        best_audio = full_audio[:window]
        for start in range(0, max(1, full_audio.shape[0] - window + 1), step):
            audio = full_audio[start : start + window]
            if audio.shape[0] < window:
                audio = np.pad(audio, (0, window - audio.shape[0]))
            score = self._score(audio)
            if score > best_score:
                best_score = score
                best_audio = audio.copy()
        return best_score, best_audio

    def _score(self, audio: np.ndarray) -> float:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.wav"
            write_wav(path, 16000, audio)
            features = clip_features(path, self._extractor)
        return float(self._scorer.predict_proba(features)[0][1])


def _record_audio(device: int | None, seconds: int) -> np.ndarray:
    audio = sd.rec(
        int(16000 * seconds),
        samplerate=16000,
        channels=1,
        dtype="int16",
        device=device,
    )
    sd.wait()
    return np.asarray(audio).reshape(-1).astype(np.int16)


def _input_index(name: str) -> int | None:
    if name.isdigit():
        return int(name)
    lowered = name.casefold()
    for index, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels", 0)) > 0:
            if lowered in str(device.get("name", "")).casefold():
                return index
    raise ValueError(f"Input device not found: {name}")


def _save_candidate(audio: np.ndarray, score: float) -> Path:
    output_dir = Path.home() / "Desktop/Maya/artifacts/wakeword_candidates"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"local_wake_{int(time.time())}_{score:.3f}.wav"
    write_wav(path, 16000, audio)
    return path
