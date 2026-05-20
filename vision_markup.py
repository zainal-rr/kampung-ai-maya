from __future__ import annotations

import re
import tempfile
from pathlib import Path

import cv2
import numpy as np


IMAGE_MARKER = "[[maya_image:"
Target = tuple[str, int, int, int]


def parse_targets(text: str) -> list[Target]:
    targets = []
    for match in re.finditer(r"TARGETS?:\s*([^\n]+)", text, re.IGNORECASE):
        line = match.group(1).strip()
        if line.lower() == "none":
            continue
        targets.extend(_parse_target_parts(line.split(";")))
    return targets


def remove_target_line(text: str) -> str:
    cleaned = re.sub(r"\s*TARGETS?:\s*[^\n]+", "", text, flags=re.IGNORECASE)
    return cleaned.strip()


def draw_visual_marks(image_bytes: bytes, targets: list[Target]) -> Path | None:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None or not targets:
        return None
    height, width = frame.shape[:2]
    if should_group_targets(targets):
        _draw_group_rectangle(frame, targets, width, height)
    else:
        for label, x_norm, y_norm, r_norm in targets:
            x = int(width * x_norm / 1000)
            y = int(height * y_norm / 1000)
            radius = int(min(width, height) * r_norm / 1000)
            if r_norm >= 120:
                _draw_rectangle(frame, label, x - radius, y - radius, x + radius, y + radius)
            else:
                _draw_circle(frame, label, x, y, radius)
    path = Path(tempfile.mkstemp(prefix="maya-sight-", suffix=".jpg")[1])
    cv2.imwrite(str(path), frame)
    return path


def parse_target(text: str) -> Target | None:
    targets = parse_targets(text)
    return targets[0] if targets else None


def draw_circle(image_bytes: bytes, target: Target) -> Path | None:
    return draw_visual_marks(image_bytes, [target])


def draw_circles(image_bytes: bytes, targets: list[Target]) -> Path | None:
    return draw_visual_marks(image_bytes, targets)


def image_marker(path: Path) -> str:
    return f"{IMAGE_MARKER}{path}]]"


def split_image_marker(text: str) -> tuple[str, Path | None]:
    match = re.search(r"\[\[maya_image:([^\]]+)\]\]", text)
    if not match:
        return text, None
    path = Path(match.group(1))
    return text.replace(match.group(0), "").strip(), path


def _parse_target_parts(parts: list[str]) -> list[Target]:
    targets = []
    for part in parts:
        fields = [field.strip() for field in part.split(",")]
        if len(fields) != 4 or fields[0].lower() == "none":
            continue
        try:
            x, y, radius = (max(0, min(1000, int(value))) for value in fields[1:])
        except ValueError:
            continue
        targets.append((fields[0], x, y, max(20, radius)))
    return targets


def should_group_targets(targets: list[Target]) -> bool:
    if len(targets) < 3:
        return False
    x1, y1, x2, y2 = target_bounds(targets)
    return x2 - x1 <= 520 and y2 - y1 <= 240


def target_bounds(targets: list[Target]) -> tuple[int, int, int, int]:
    left = min(max(0, x - radius) for _, x, _, radius in targets)
    top = min(max(0, y - radius) for _, _, y, radius in targets)
    right = max(min(1000, x + radius) for _, x, _, radius in targets)
    bottom = max(min(1000, y + radius) for _, _, y, radius in targets)
    return left, top, right, bottom


def target_group_label(targets: list[Target]) -> str:
    labels = [target[0].strip() for target in targets if target[0].strip()]
    if not labels:
        return "area"
    first_words = [label.split()[0].lower() for label in labels if label.split()]
    if first_words and all(word == first_words[0] for word in first_words):
        return f"{first_words[0].upper()} group"
    return "group"


def _draw_circle(frame, label: str, x: int, y: int, radius: int) -> None:
    color = (0, 255, 255)
    cv2.circle(frame, (x, y), max(20, radius), color, 6)
    cv2.putText(
        frame,
        label[:28],
        (max(0, x - 40), max(32, y - radius - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        3,
    )


def _draw_group_rectangle(frame, targets: list[Target], width: int, height: int) -> None:
    x1, y1, x2, y2 = target_bounds(targets)
    left = int(width * x1 / 1000)
    top = int(height * y1 / 1000)
    right = int(width * x2 / 1000)
    bottom = int(height * y2 / 1000)
    _draw_rectangle(frame, target_group_label(targets), left, top, right, bottom)


def _draw_rectangle(frame, label: str, left: int, top: int, right: int, bottom: int) -> None:
    color = (0, 255, 255)
    pad = 8
    height, width = frame.shape[:2]
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(width - 1, right + pad)
    bottom = min(height - 1, bottom + pad)
    cv2.rectangle(frame, (left, top), (right, bottom), color, 6)
    cv2.putText(
        frame,
        label[:28],
        (left, max(32, top - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        3,
    )
