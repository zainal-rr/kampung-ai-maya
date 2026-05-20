from __future__ import annotations

import os
import time

from dotenv import load_dotenv

load_dotenv()

os.environ["ENABLE_VISION_CAMERA"] = "1"
os.environ["ENABLE_IMAC_CHANNEL"] = "1"

from vision import VisionNode


def main() -> None:
    vision = VisionNode()
    if vision.camera_index == vision.imac_camera_index:
        raise SystemExit("Refusing to probe the blocked iMac camera index.")

    print("== Kampung AI Vision Probe ==")
    print("camera_name:", vision.camera_name)
    print("camera_index:", vision.camera_index)
    print("blocked_imac_index:", vision.imac_camera_index)
    vision.start()
    try:
        time.sleep(2.5)
        print("real_camera_enabled:", vision.real_camera_enabled)
        print("is_present:", vision.is_present)
        print("analysis:", vision.get_frame_analysis())
    finally:
        vision.stop()


if __name__ == "__main__":
    main()
