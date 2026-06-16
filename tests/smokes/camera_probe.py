from __future__ import annotations

import time

from dotenv import load_dotenv

load_dotenv()

import cv2

from vision import VisionNode


def main() -> None:
    vision = VisionNode()
    if vision.camera_index == vision.imac_camera_index:
        raise SystemExit("Refusing to probe the blocked iMac camera index.")

    print("== Kampung AI Camera Probe ==")
    print("camera_name:", vision.camera_name)
    print("camera_index:", vision.camera_index)
    print("blocked_imac_index:", vision.imac_camera_index)

    cap = cv2.VideoCapture(vision.camera_index)
    if not cap.isOpened():
        print("open_ok: False")
        print("camera_status: unavailable or permission blocked")
        return

    frame = None
    for _ in range(10):
        ok, candidate = cap.read()
        if ok and candidate is not None:
            frame = candidate
            break
        time.sleep(0.2)
    cap.release()

    if frame is None:
        print("read_ok: False")
        print("camera_status: opened but no frame received")
        return

    blocked = vision._looks_blocked(frame)
    brightness = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()
    print("read_ok: True")
    print("frame_shape:", tuple(frame.shape))
    print("mean_brightness:", round(float(brightness), 2))
    print("lens_blocked:", blocked)
    print("camera_status:", "blocked" if blocked else "visible")


if __name__ == "__main__":
    main()
