from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import sounddevice as sd

from maya_core.sounddevice_audio import resolve_first_output, resolve_sounddevice_output


SAMPLE_RATE = 16000


@dataclass(frozen=True)
class AudioSample:
    label: str
    audio: np.ndarray
    embedding: list[float]
    rms: float
    peak: float


def record_usable_sample(label: str, *, seconds: float, device: int | None, max_attempts: int = 3) -> tuple[np.ndarray, dict[str, float]]:
    last_quality: dict[str, float] = {"rms": 0.0, "peak": 0.0}
    for attempt in range(1, max_attempts + 1):
        suffix = f" attempt {attempt}/{max_attempts}" if attempt > 1 else ""
        audio = record_countdown(label + suffix, seconds=seconds, device=device)
        quality = audio_quality(audio)
        print(f"Audio level: rms={quality['rms']:.4f} peak={quality['peak']:.4f}")
        last_quality = quality
        if audio_quality_is_usable(quality):
            return audio, quality
        print("That sample was too quiet or mostly silence. Please speak closer to the mic for the retry.")
    raise RuntimeError(
        f"Voiceprint sample '{label}' was too quiet after {max_attempts} attempts "
        f"(last rms={last_quality['rms']:.4f}, peak={last_quality['peak']:.4f})."
    )


def record_countdown(label: str, *, seconds: float, device: int | None) -> np.ndarray:
    print(f"\nGet ready for {label}.")
    for remaining in (3, 2, 1):
        print(f"Recording in {remaining}...")
        time.sleep(1)
    print("Speak now.")
    audio = sd.rec(int(SAMPLE_RATE * seconds), samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=device)
    sd.wait()
    print("Captured.")
    return np.asarray(audio, dtype=np.float32).reshape(-1)


def audio_quality(audio: np.ndarray) -> dict[str, float]:
    clean = np.nan_to_num(np.asarray(audio, dtype=np.float32).reshape(-1))
    if clean.size == 0:
        return {"rms": 0.0, "peak": 0.0}
    return {
        "rms": float(np.sqrt(np.mean(np.square(clean)))),
        "peak": float(np.max(np.abs(clean))),
    }


def audio_quality_is_usable(quality: dict[str, float]) -> bool:
    return quality["rms"] >= 0.003 and quality["peak"] >= 0.015


def record_replay(
    owner_audio: np.ndarray,
    *,
    seconds: float,
    device: int | None,
    output_device_name: str,
) -> np.ndarray | None:
    output_device = resolve_sounddevice_output(output_device_name) if output_device_name else None
    output = resolve_first_output() if output_device is None else None
    resolved_output = output_device if output_device is not None else (output.device if output else None)
    if resolved_output is None:
        print("Skipping replay check: no output device available.")
        return None
    output_label = output_device_name or (output.label if output else "configured output")
    print(f"\nRecording-replay check. I will play one owner sample through {output_label} and re-record it through the mic.")
    time.sleep(1)
    frames = int(SAMPLE_RATE * seconds)
    playback = fit_audio_length(owner_audio, frames).reshape(-1, 1)
    devices = (device, resolved_output) if device is not None else resolved_output
    recorded = sd.playrec(playback, samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=devices)
    sd.wait()
    print("Replay check captured.")
    return np.asarray(recorded, dtype=np.float32).reshape(-1)


def fit_audio_length(audio: np.ndarray, frames: int) -> np.ndarray:
    clean = np.nan_to_num(np.asarray(audio, dtype=np.float32).reshape(-1))
    if clean.size >= frames:
        return clean[:frames]
    return np.pad(clean, (0, frames - clean.size))


def quality_stats(samples: list[AudioSample], stats_fn) -> dict[str, Any]:
    if not samples:
        return {"count": 0}
    return {
        "count": len(samples),
        "rms": stats_fn([sample.rms for sample in samples]),
        "peak": stats_fn([sample.peak for sample in samples]),
    }
