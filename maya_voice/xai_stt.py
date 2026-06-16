from __future__ import annotations

from pathlib import Path

try:
    import requests
except ImportError:
    requests = None


def xai_transcribe_file(api_key: str, audio_path: Path, language: str | None = None) -> str:
    if requests is None:
        raise RuntimeError("requests is required for xAI STT.")

    data = {"format": "true", "language": language or "auto"}

    with audio_path.open("rb") as audio_file:
        response = requests.post(
            "https://api.x.ai/v1/stt",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (audio_path.name, audio_file, "audio/wav")},
            data=data,
            timeout=30,
        )
    response.raise_for_status()
    payload = response.json()
    return payload.get("text", "").strip()
