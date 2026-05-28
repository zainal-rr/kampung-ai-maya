from __future__ import annotations

import os


def frame_blocked(frame) -> bool:
    brightness, flatness = frame_metrics(frame)
    darkness = float(os.getenv("MAYA_CAMERA_BLOCKED_DARKNESS_THRESHOLD", "8"))
    flat_max = float(os.getenv("MAYA_CAMERA_BLOCKED_FLAT_BRIGHTNESS_MAX", "45"))
    flat_limit = float(os.getenv("MAYA_CAMERA_BLOCKED_STDDEV_THRESHOLD", "3"))
    return brightness < darkness or (brightness < flat_max and flatness < flat_limit)


def frame_metrics(frame) -> tuple[float, float]:
    import cv2

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(gray.mean()), float(gray.std())
