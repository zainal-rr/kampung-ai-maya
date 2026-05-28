from __future__ import annotations

import json
import os
from pathlib import Path

from maya_eye_tracker import TargetTracker, target_signature
from vision_markup import Target, should_group_targets, target_group_label


def target_file() -> Path:
    return Path(os.getenv("MAYA_EYE_PREVIEW_TARGET_FILE", "/tmp/maya-eye-target.json"))


def set_preview_targets(targets: list[Target]) -> None:
    payload = {"targets": [_target_payload(target) for target in targets]}
    target_file().write_text(json.dumps(payload), encoding="utf-8")


def set_preview_target(target: Target) -> None:
    set_preview_targets([target])


def clear_preview_target() -> None:
    target_file().unlink(missing_ok=True)


def draw_preview_targets(frame, trackers: dict[str, TargetTracker]) -> None:
    targets = _read_targets()
    if _draw_group_if_needed(frame, trackers, targets):
        return
    active = set()
    for target in targets:
        signature = target_signature(target)
        active.add(signature)
        tracker = trackers.setdefault(signature, TargetTracker())
        tracked = tracker.update(frame, target)
        if tracked:
            _draw_tracked(frame, tracked)
    _remove_inactive_trackers(trackers, active)


def _draw_tracked(frame, tracked: Target) -> None:
    import cv2

    label, x, y, radius = tracked
    if radius >= 120:
        _draw_rectangle(frame, label, x - radius, y - radius, x + radius, y + radius)
        return
    color = (0, 255, 255)
    cv2.circle(frame, (x, y), radius, color, 6)
    cv2.putText(
        frame,
        label[:28],
        (max(0, x - 40), max(36, y - radius - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        3,
    )


def _draw_group_if_needed(frame, trackers: dict[str, TargetTracker], targets: list[dict]) -> bool:
    tuples = [_target_tuple(target) for target in targets]
    tuples = [target for target in tuples if target]
    if not should_group_targets(tuples):
        return False
    tracked = []
    active = set()
    for target in targets:
        signature = target_signature(target)
        active.add(signature)
        tracker = trackers.setdefault(signature, TargetTracker())
        match = tracker.update(frame, target)
        if match:
            tracked.append(match)
    _remove_inactive_trackers(trackers, active)
    if tracked:
        _draw_group_rectangle(frame, tracked)
    return True


def _draw_group_rectangle(frame, tracked: list[Target]) -> None:
    x1 = min(x - radius for _, x, _, radius in tracked)
    y1 = min(y - radius for _, _, y, radius in tracked)
    x2 = max(x + radius for _, x, _, radius in tracked)
    y2 = max(y + radius for _, _, y, radius in tracked)
    _draw_rectangle(frame, target_group_label(tracked), x1, y1, x2, y2)


def _draw_rectangle(frame, label: str, left: int, top: int, right: int, bottom: int) -> None:
    import cv2

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
        (left, max(36, top - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        3,
    )


def _remove_inactive_trackers(trackers: dict[str, TargetTracker], active: set[str]) -> None:
    for signature in list(trackers):
        if signature not in active:
            del trackers[signature]


def _read_targets() -> list[dict]:
    try:
        payload = json.loads(target_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload.get("targets"), list):
        return [item for item in payload["targets"] if _valid_target(item)]
    return [payload] if _valid_target(payload) else []


def _valid_target(payload: dict) -> bool:
    required = {"label", "x", "y", "radius"}
    return isinstance(payload, dict) and required.issubset(payload)


def _target_tuple(target: dict) -> Target | None:
    if not _valid_target(target):
        return None
    return str(target["label"]), int(target["x"]), int(target["y"]), int(target["radius"])


def _target_payload(target: Target) -> dict:
    label, x, y, radius = target
    return {"label": label, "x": x, "y": y, "radius": radius}
