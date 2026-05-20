from __future__ import annotations

import time
from dataclasses import dataclass

import cv2

from vision import VisionNode


@dataclass(frozen=True)
class VisionSnapshot:
    visible: bool
    status: str
    image_bytes: bytes | None = None
    brightness: float | None = None


class CiscoVisionService:
    def __init__(self):
        self.vision = VisionNode()

    def capture_once(self) -> VisionSnapshot:
        if self.vision.camera_index == self.vision.imac_camera_index:
            return VisionSnapshot(False, "I refuse to use the built in iMac camera.")

        cap = cv2.VideoCapture(self.vision.camera_index)
        if not cap.isOpened():
            return VisionSnapshot(False, f"{self.vision.camera_name} is unavailable or permission blocked.")
        try:
            frame = self._read_frame(cap)
            if frame is None:
                return VisionSnapshot(False, f"{self.vision.camera_name} privacy block closed or no visible frame.")
            brightness = self._brightness(frame)
            if self.vision._looks_blocked(frame):
                return VisionSnapshot(False, f"{self.vision.camera_name} lens appears blocked.", brightness=brightness)
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if not ok:
                return VisionSnapshot(False, "I could see a frame, but could not prepare it for description.")
            return VisionSnapshot(True, f"{self.vision.camera_name} frame visible.", encoded.tobytes(), brightness)
        finally:
            cap.release()

    @staticmethod
    def _read_frame(cap):
        for _ in range(10):
            ok, frame = cap.read()
            if ok and frame is not None:
                return frame
            time.sleep(0.2)
        return None

    @staticmethod
    def _brightness(frame) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return round(float(gray.mean()), 2)
