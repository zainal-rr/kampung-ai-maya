from __future__ import annotations

from dataclasses import dataclass

from storage import get_history
from travel_parameters import extract_destination, normalize
from word_quality import detect_word_intent


@dataclass(frozen=True)
class ArtifactParameterResolution:
    topic: str
    question: str = ""
    note: str = ""


async def resolve_artifact_parameters(
    db_path: str,
    artifact_type: str,
    topic: str,
    channel: str,
) -> ArtifactParameterResolution:
    if not _needs_travel_destination(artifact_type, topic):
        return ArtifactParameterResolution(topic=topic)
    explicit = extract_destination(topic)
    if explicit:
        return ArtifactParameterResolution(topic=topic)
    recent = await _recent_destination(db_path)
    if recent:
        resolved = _prepend_destination(topic, recent)
        return ArtifactParameterResolution(
            topic=resolved,
            note=f"Using {recent} from recent context because the request did not name a destination.",
        )
    return ArtifactParameterResolution(
        topic=topic,
        question="Which city or destination should I use for the trip document?",
    )


def _needs_travel_destination(artifact_type: str, topic: str) -> bool:
    lowered = normalize(topic)
    if artifact_type == "docx":
        return detect_word_intent(topic) == "travel_itinerary"
    if artifact_type in {"xlsx", "pptx"}:
        return any(marker in lowered for marker in ("travel", "trip", "itinerary", "food trip", "restaurant"))
    return False


async def _recent_destination(db_path: str) -> str:
    try:
        history = await get_history(db_path, 1, limit=12)
    except Exception:
        return ""
    for turn in reversed(history):
        if turn.get("role") not in {"user", "assistant"}:
            continue
        destination = extract_destination(turn.get("content", ""))
        if destination:
            return destination
    return ""


def _prepend_destination(topic: str, destination: str) -> str:
    clean_topic = str(topic or "").strip()
    if not clean_topic:
        return destination
    lowered = clean_topic.lower()
    if lowered.startswith(destination.lower()):
        return clean_topic
    if lowered.startswith(("solo ", "two ", "2-day ", "2 day ")):
        return f"{destination} {clean_topic}"
    return f"{destination} {clean_topic}"
