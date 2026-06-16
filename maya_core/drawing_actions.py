from __future__ import annotations

import asyncio
import html
import os
import re
from pathlib import Path

from maya_core.gemini_image import generate_gemini_image
from office_files import safe_slug
from utils import OSBridge
from workspace_paths import workspace_dir


class DrawingActionRouter:
    def __init__(self, workspace: Path | None = None, bridge: OSBridge | None = None):
        self.workspace = workspace or workspace_dir("drawings")
        self.bridge = bridge or OSBridge()

    async def handle(self, text: str, channel: str) -> str | None:
        subject = _drawing_subject(text)
        if not subject:
            return None
        if _wants_gemini(text):
            generated = await self._try_gemini(subject, channel)
            if generated:
                return generated
        path = self.workspace / f"{safe_slug(subject)}.svg"
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, _svg_for(subject), "utf-8")
        return await self._deliver(path, channel, f"I drew {subject} at {path}.")

    async def _try_gemini(self, subject: str, channel: str) -> str | None:
        if os.getenv("ENABLE_GEMINI_IMAGE_GENERATION", "0") != "1":
            return None
        path = self.workspace / f"{safe_slug(subject)}.png"
        try:
            await generate_gemini_image(f"Create a clear image of {subject}.", path)
        except Exception as exc:
            return f"I could not generate that image with Gemini yet: {exc}"
        return await self._deliver(path, channel, f"I generated {subject} with Gemini image generation at {path}.")

    async def _deliver(self, path: Path, channel: str, message: str) -> str:
        if channel == "telegram":
            return f"{message}\n[file:{path}]"
        try:
            await asyncio.to_thread(self.bridge.open_file, str(path), None)
        except Exception as exc:
            return f"{message} I could not open it on the iMac yet: {exc}"
        return f"{message} I opened it on the iMac."


def _drawing_subject(text: str) -> str | None:
    match = re.match(
        r"^(?:draw|sketch|create drawing of|make drawing of|create diagram of|make diagram of|"
        r"generate image of|create image of|make image of)\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    subject = re.sub(r"^(?:a|an|the)\s+", "", match.group(1).strip(), flags=re.IGNORECASE)
    return subject.strip(" .")


def _wants_gemini(text: str) -> bool:
    lowered = text.lower()
    markers = ("gemini", "nano banana", "generate image", "photo", "realistic", "artistic")
    return any(marker in lowered for marker in markers)


def _svg_for(subject: str) -> str:
    lowered = subject.lower()
    if "moon" in lowered:
        return _moon_svg(subject)
    if "network" in lowered or "diagram" in lowered:
        return _network_svg(subject)
    return _generic_svg(subject)


def _moon_svg(subject: str) -> str:
    title = html.escape(subject.title())
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#10141f"/>
  <circle cx="256" cy="256" r="132" fill="#f4e8b8"/>
  <circle cx="306" cy="218" r="132" fill="#10141f"/>
  <text x="256" y="450" fill="#f4e8b8" font-size="28" text-anchor="middle" font-family="Arial">{title}</text>
</svg>
"""


def _network_svg(subject: str) -> str:
    title = html.escape(subject.title())
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 420">
  <rect width="720" height="420" fill="#f7f7f2"/>
  <text x="360" y="46" font-size="26" text-anchor="middle" font-family="Arial" fill="#24324a">{title}</text>
  <line x1="180" y1="190" x2="360" y2="130" stroke="#4f7cac" stroke-width="5"/>
  <line x1="360" y1="130" x2="540" y2="190" stroke="#4f7cac" stroke-width="5"/>
  <line x1="360" y1="130" x2="360" y2="300" stroke="#4f7cac" stroke-width="5"/>
  <rect x="300" y="94" width="120" height="72" rx="8" fill="#ffffff" stroke="#24324a" stroke-width="4"/>
  <circle cx="180" cy="190" r="48" fill="#ffffff" stroke="#24324a" stroke-width="4"/>
  <circle cx="540" cy="190" r="48" fill="#ffffff" stroke="#24324a" stroke-width="4"/>
  <rect x="300" y="270" width="120" height="60" rx="8" fill="#ffffff" stroke="#24324a" stroke-width="4"/>
  <text x="360" y="138" font-size="18" text-anchor="middle" font-family="Arial">Router</text>
  <text x="180" y="198" font-size="18" text-anchor="middle" font-family="Arial">Laptop</text>
  <text x="540" y="198" font-size="18" text-anchor="middle" font-family="Arial">Phone</text>
  <text x="360" y="306" font-size="18" text-anchor="middle" font-family="Arial">Switch</text>
</svg>
"""


def _generic_svg(subject: str) -> str:
    title = html.escape(subject.title())
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#f3f0e8"/>
  <circle cx="256" cy="230" r="112" fill="#8db7e8" stroke="#24324a" stroke-width="8"/>
  <text x="256" y="420" font-size="30" text-anchor="middle" font-family="Arial" fill="#24324a">{title}</text>
</svg>
"""
