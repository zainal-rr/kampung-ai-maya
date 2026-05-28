from __future__ import annotations

import asyncio
import html
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from office_files import safe_slug
from utils import OSBridge
from workspace_paths import maya_workspace_root


VISUAL_WORKFLOW_RUN_ID = "visual_workflow_actions"


@dataclass
class VisualWorkflowResult:
    source_path: Path
    visual_path: Path
    renderer: str


class VisualWorkflowRenderer:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.output_dir = maya_workspace_root() / "architecture"

    async def handle(self, text: str, channel: str) -> str | None:
        subject = visual_workflow_subject(text)
        if not subject:
            return None
        result = await self.create(subject)
        await record_structured_artifact(
            self.db_path,
            VISUAL_WORKFLOW_RUN_ID,
            local_artifact("diagram", str(result.visual_path), f"Visual workflow for {subject}", "visual_workflow"),
        )
        await record_structured_artifact(
            self.db_path,
            VISUAL_WORKFLOW_RUN_ID,
            local_artifact("note", str(result.source_path), f"Mermaid source for {subject}", "visual_workflow"),
        )
        if channel == "telegram":
            return (
                f"Done. I created a visual workflow using {result.renderer}.\n"
                f"[file:{result.visual_path}]\n[file:{result.source_path}]"
            )
        try:
            await asyncio.to_thread(self.bridge.open_file, str(result.visual_path), None)
            return f"Done. I created a visual workflow using {result.renderer} and opened it on the iMac."
        except Exception as exc:
            return f"Done. I created a visual workflow at {result.visual_path}, but I could not open it: {exc}"

    async def create(self, subject: str) -> VisualWorkflowResult:
        await asyncio.to_thread(self.output_dir.mkdir, parents=True, exist_ok=True)
        slug = safe_slug(subject)[:80] or "visual-workflow"
        source_path = self.output_dir / f"{slug}.mmd"
        svg_path = self.output_dir / f"{slug}.svg"
        mermaid = mermaid_for_subject(subject)
        await asyncio.to_thread(source_path.write_text, mermaid, "utf-8")
        renderer = await self._render_mermaid(source_path, svg_path)
        if not svg_path.exists():
            await asyncio.to_thread(svg_path.write_text, fallback_svg(subject, mermaid), "utf-8")
            renderer = "built in SVG fallback"
        await record_structured_artifact(
            self.db_path,
            VISUAL_WORKFLOW_RUN_ID,
            local_artifact("diagram", str(svg_path), f"Visual workflow for {subject}", "visual_workflow"),
        )
        await record_structured_artifact(
            self.db_path,
            VISUAL_WORKFLOW_RUN_ID,
            local_artifact("note", str(source_path), f"Mermaid source for {subject}", "visual_workflow"),
        )
        return VisualWorkflowResult(source_path, svg_path, renderer)

    async def _render_mermaid(self, source_path: Path, output_path: Path) -> str:
        mmdc = shutil.which("mmdc")
        if mmdc:
            try:
                await asyncio.to_thread(
                    subprocess.run,
                    [
                        mmdc,
                        "-i",
                        str(source_path),
                        "-o",
                        str(output_path),
                        "-b",
                        "transparent",
                        "-t",
                        "dark",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return "Mermaid CLI"
            except Exception:
                pass
        return "built in SVG fallback"


def visual_workflow_subject(text: str) -> str | None:
    cleaned = " ".join(text.strip().split())
    patterns = (
        r"^(?:map this idea visually|map this visually|make a visual workflow for this|create an architecture diagram for this|make a mermaid visual for this|turn this into a flow diagram)\s*:?\s*(.*)$",
        r"^(?:make|create|draw)\s+(?:an?\s+)?(?:visual workflow|workflow diagram|architecture diagram|mermaid visual|flow diagram)\s+(?:for|about|on)?\s*(.*)$",
    )
    for pattern in patterns:
        match = re.match(pattern, cleaned, re.IGNORECASE)
        if match:
            subject = match.group(1).strip(" .:")
            return subject or "Maya workflow"
    return None


def mermaid_for_subject(subject: str) -> str:
    labels = _labels(subject)
    title = _node_text(subject.title(), 42)
    lines = [
        "flowchart TD",
        f'    A["{title}"] --> B{{"Input or trigger"}}',
    ]
    for index, label in enumerate(labels[:4], start=1):
        node = chr(ord("B") + index)
        lines.append(f'    B --> {node}["{_node_text(label, 34)}"]')
        lines.append(f'    {node} --> {node}1["{_node_text(_action_for(label), 34)}"]')
    lines.append('    B --> Z["Review and improve"]')
    lines.append('    Z --> ZA["Save source and rendered visual"]')
    return "\n".join(lines) + "\n"


def fallback_svg(subject: str, mermaid: str) -> str:
    labels = _labels(subject)[:4]
    width = 1600
    height = 1000
    boxes = [
        (650, 80, 300, 72, subject.title()[:54]),
        (655, 215, 290, 90, "Input or trigger"),
    ]
    x_positions = [110, 465, 820, 1175]
    for idx, label in enumerate(labels):
        x = x_positions[idx]
        boxes.append((x, 430, 280, 78, _node_text(label, 32)))
        boxes.append((x, 610, 280, 78, _node_text(_action_for(label), 32)))
    boxes.append((650, 790, 300, 78, "Review and improve"))
    rects = []
    lines = [
        _line(800, 152, 800, 215),
        _line(800, 305, 800, 370),
        _line(800, 688, 800, 790),
    ]
    for x in x_positions[: len(labels)]:
        lines.append(_line(800, 370, x + 140, 430))
        lines.append(_line(x + 140, 508, x + 140, 610))
        lines.append(_line(x + 140, 688, 800, 790))
    for x, y, w, h, text in boxes:
        rects.append(_box(x, y, w, h, text))
    title = html.escape(subject.title()[:80])
    source_comment = html.escape(mermaid[:800])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="#202020"/>
  <text x="48" y="64" fill="#f5f5f5" font-size="42" font-family="Arial, Helvetica, sans-serif" font-weight="700">{title}</text>
  <g stroke="#c9c9c9" stroke-width="2" fill="none">{''.join(lines)}</g>
  <g>{''.join(rects)}</g>
  <desc>{source_comment}</desc>
</svg>
'''


def _labels(subject: str) -> list[str]:
    cleaned = re.sub(r"\b(and|then|with|plus)\b", ",", subject, flags=re.IGNORECASE)
    parts = [part.strip(" .:;") for part in re.split(r"[,/]", cleaned) if part.strip(" .:;")]
    if len(parts) >= 2:
        return parts[:6]
    words = [word for word in re.findall(r"[A-Za-z0-9]+", subject) if len(word) > 2]
    if len(words) >= 4:
        return [" ".join(words[i : i + 2]) for i in range(0, min(len(words), 8), 2)]
    return ["Capture idea", "Structure path", "Render visual", "Review result"]


def _action_for(label: str) -> str:
    lowered = label.lower()
    if "telegram" in lowered:
        return "Route remote request"
    if "voice" in lowered or "imac" in lowered:
        return "Use local body context"
    if "file" in lowered or "document" in lowered:
        return "Create artifact"
    if "memory" in lowered:
        return "Save useful context"
    if "call" in lowered:
        return "Use normal iMac voice"
    return "Decide next step"


def _node_text(text: str, limit: int) -> str:
    clean = html.unescape(" ".join(str(text).split())).replace('"', "'")
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rsplit(" ", 1)[0] or clean[:limit]


def _line(x1: int, y1: int, x2: int, y2: int) -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>'


def _box(x: int, y: int, w: int, h: int, text: str) -> str:
    escaped = html.escape(text)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#333333" stroke="#454545"/>'
        f'<text x="{x + w / 2:.0f}" y="{y + h / 2 + 7:.0f}" fill="#f5f5f5" font-size="24" '
        f'font-family="Arial, Helvetica, sans-serif" text-anchor="middle">{escaped}</text>'
    )
