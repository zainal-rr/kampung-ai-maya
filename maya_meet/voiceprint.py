from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from maya_core.provenance import make_provenance


@dataclass(frozen=True)
class VoiceprintDecision:
    source_kind: str
    confidence: float
    threshold: float
    reason_code: str
    enrollment_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "confidence": round(self.confidence, 6),
            "threshold": round(self.threshold, 6),
            "reason_code": self.reason_code,
            "enrollment_id": self.enrollment_id,
        }

    def provenance(self):
        return make_provenance(self.source_kind, source_id=self.enrollment_id)


def verify_voiceprint(enrollment: dict[str, Any], sample_embedding: list[float]) -> VoiceprintDecision:
    if enrollment.get("status") != "enrolled":
        return VoiceprintDecision("other_speaker", 0.0, 1.0, "voiceprint_not_enrolled")
    threshold = float(enrollment.get("threshold") or 0.88)
    enrollment_id = str(enrollment.get("enrollment_id") or "")
    enrolled_embedding = _coerce_embedding(enrollment.get("embedding") or [])
    sample = _coerce_embedding(sample_embedding or [])
    if enrolled_embedding is None or sample is None:
        return VoiceprintDecision("other_speaker", 0.0, threshold, "voiceprint_malformed_vector", enrollment_id)
    if not enrolled_embedding or not sample:
        return VoiceprintDecision("other_speaker", 0.0, threshold, "missing_voiceprint_sample", enrollment_id)
    if len(enrolled_embedding) != len(sample):
        return VoiceprintDecision("other_speaker", 0.0, threshold, "voiceprint_dimension_mismatch", enrollment_id)
    confidence = cosine_similarity(enrolled_embedding, sample)
    if confidence >= threshold:
        return VoiceprintDecision("owner_voice_meeting", confidence, threshold, "voiceprint_owner_verified", enrollment_id)
    return VoiceprintDecision("other_speaker", confidence, threshold, "voiceprint_low_confidence", enrollment_id)


def _coerce_embedding(values: Any) -> list[float] | None:
    if not isinstance(values, (list, tuple)):
        return None
    coerced: list[float] = []
    try:
        for value in values:
            number = float(value)
            if not math.isfinite(number):
                return None
            coerced.append(number)
    except (TypeError, ValueError):
        return None
    return coerced


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    if not left:
        return 0.0
    dot = sum(x * y for x, y in zip(left, right))
    norm_a = math.sqrt(sum(x * x for x in left))
    norm_b = math.sqrt(sum(y * y for y in right))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))
