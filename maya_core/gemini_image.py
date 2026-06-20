from __future__ import annotations

import asyncio
import base64
import io
import os
from pathlib import Path

from google import genai
from PIL import Image


async def generate_gemini_image(prompt: str, path: Path) -> Path:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is required for Gemini image generation.")
    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    return await asyncio.to_thread(_generate_sync, api_key, model, prompt, path)


def _generate_sync(api_key: str, model: str, prompt: str, path: Path) -> Path:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    path.parent.mkdir(parents=True, exist_ok=True)
    for part in _response_parts(response):
        inline_data = getattr(part, "inline_data", None)
        if not inline_data:
            continue
        if hasattr(part, "as_image"):
            image = part.as_image()
        else:
            data = inline_data.data
            if isinstance(data, str):
                try:
                    data = base64.b64decode(data)
                except Exception:
                    data = data.encode("latin1")
            image = Image.open(io.BytesIO(data))
        image.save(path)
        return path
    raise RuntimeError("Gemini did not return image data.")


def _response_parts(response) -> list:
    direct = getattr(response, "parts", None)
    if direct:
        return list(direct)
    parts = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        parts.extend(getattr(content, "parts", []) or [])
    return parts
