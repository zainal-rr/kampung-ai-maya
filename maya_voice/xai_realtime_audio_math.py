from __future__ import annotations

from array import array
import math


def pcm_rms(audio: bytes) -> float:
    if len(audio) < 2:
        return 0.0
    try:
        samples = array("h")
        samples.frombytes(audio[: len(audio) - (len(audio) % 2)])
        if not samples:
            return 0.0
        return round(math.sqrt(sum(sample * sample for sample in samples) / len(samples)), 2)
    except Exception:
        return 0.0
