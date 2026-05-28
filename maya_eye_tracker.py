from __future__ import annotations

import os


class TargetTracker:
    def __init__(self):
        self.signature = ""
        self.template = None
        self.radius = 30
        self.threshold = float(os.getenv("MAYA_EYE_TRACK_THRESHOLD", "0.45"))

    def update(self, frame, target: dict | None) -> tuple[str, int, int, int] | None:
        if not target:
            self._clear()
            return None
        signature = self._signature(target)
        if signature != self.signature or self.template is None:
            self._seed(frame, target, signature)
            return self._target_box(frame, target)
        return self._match(frame, target)

    def _match(self, frame, target: dict) -> tuple[str, int, int, int] | None:
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.template is None or self.template.size == 0:
            return None
        if gray.shape[0] < self.template.shape[0] or gray.shape[1] < self.template.shape[1]:
            return None
        _, score, _, loc = cv2.minMaxLoc(cv2.matchTemplate(gray, self.template, cv2.TM_CCOEFF_NORMED))
        if score < self.threshold:
            return None
        height, width = self.template.shape[:2]
        x = loc[0] + width // 2
        y = loc[1] + height // 2
        return str(target["label"]), x, y, self.radius

    def _seed(self, frame, target: dict, signature: str) -> None:
        import cv2

        label, x, y, radius = self._target_box(frame, target)
        crop = self._crop(frame, x, y, radius)
        if crop is None:
            self._clear()
            return
        self.signature = signature
        self.radius = radius
        self.template = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _target_box(frame, target: dict) -> tuple[str, int, int, int]:
        height, width = frame.shape[:2]
        x = int(width * int(target["x"]) / 1000)
        y = int(height * int(target["y"]) / 1000)
        radius = max(24, int(min(width, height) * int(target["radius"]) / 1000))
        return str(target["label"]), x, y, radius

    @staticmethod
    def _crop(frame, x: int, y: int, radius: int):
        height, width = frame.shape[:2]
        pad = max(32, radius)
        left, right = max(0, x - pad), min(width, x + pad)
        top, bottom = max(0, y - pad), min(height, y + pad)
        if right - left < 12 or bottom - top < 12:
            return None
        return frame[top:bottom, left:right]

    @staticmethod
    def _signature(target: dict) -> str:
        return target_signature(target)

    def _clear(self) -> None:
        self.signature = ""
        self.template = None


def target_signature(target: dict) -> str:
    return f"{target.get('label')}:{target.get('x')}:{target.get('y')}:{target.get('radius')}"
