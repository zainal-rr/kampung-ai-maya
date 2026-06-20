import os

import cv2
import threading
import time

from maya_core.vision_blocked import frame_blocked

class VisionNode:
    """
    VisionNode handles camera input using OpenCV and MediaPipe.
    Detects user presence and simple hand gestures in a non-blocking thread.
    """
    def __init__(self, camera_index=None):
        self.external_camera_index = int(os.getenv("MAYA_EXTERNAL_CAMERA_INDEX", "0"))
        self.imac_camera_index = int(os.getenv("MAYA_IMAC_CAMERA_INDEX", "1"))
        self.camera_name = os.getenv("MAYA_EXTERNAL_CAMERA_NAME", "Cisco Desk Camera 4K")
        self.real_camera_requested = os.getenv("ENABLE_VISION_CAMERA", "0") == "1"
        self.local_activation_enabled = (
            os.getenv("ENABLE_IMAC_CHANNEL", "0") == "1"
            or os.getenv("ENABLE_EXTERNAL_CAMERA_ADAPTER", "0") == "1"
        )
        self.real_camera_enabled = self.real_camera_requested and self.local_activation_enabled
        self.darkness_threshold = float(os.getenv("MAYA_CAMERA_BLOCKED_DARKNESS_THRESHOLD", "8"))
        requested_index = self.external_camera_index if camera_index is None else int(camera_index)
        if os.getenv("MAYA_DISABLE_IMAC_CAMERA", "1") == "1" and requested_index == self.imac_camera_index:
            requested_index = self.external_camera_index
        self.camera_index = requested_index
        self.cap = None
        self.is_present = True
        self.gesture_active = False
        self.last_analysis = "Mock Vision Active"
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        if not self.real_camera_enabled:
            self.is_present = True
            self.last_analysis = self._mock_status()
            return
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            self.is_present = False
            self.last_analysis = f"{self.camera_name} unavailable"
            self.cap.release()
            self.cap = None
            return
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
        if self.cap:
            self.cap.release()
            self.cap = None

    def _is_palm(self, hand_landmarks):
        return False

    def _run_loop(self):
        while self.running and self.cap:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                self.is_present = False
                self.last_analysis = f"{self.camera_name} privacy block closed or no visible frame"
                time.sleep(1)
                continue
            if self._looks_blocked(frame):
                self.is_present = False
                self.last_analysis = f"{self.camera_name} lens appears blocked"
            else:
                self.is_present = True
                self.last_analysis = f"{self.camera_name} frame visible"
            time.sleep(1)

    def _looks_blocked(self, frame) -> bool:
        return frame_blocked(frame)

    def _mock_status(self) -> str:
        if self.real_camera_requested:
            return f"Vision standby ({self.camera_name}, local activation disabled)"
        return f"Mock Vision Active ({self.camera_name}, iMac camera disabled)"

    def get_frame_analysis(self):
        return self.last_analysis

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
