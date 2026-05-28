from __future__ import annotations

import time
from pathlib import Path

import cv2
from dotenv import load_dotenv

from workspace_paths import workspace_dir


def main() -> None:
    load_dotenv()
    output_dir = workspace_dir("screenshots", create=True) / "camera-index-probe"
    output_dir.mkdir(parents=True, exist_ok=True)
    print("== Kampung AI Camera Index Probe ==")
    print(f"output_dir: {output_dir}")
    found = False
    for index in range(6):
        result = _probe(index, output_dir)
        print(result)
        found = found or "read_ok=True" in result
    if not found:
        print("No readable camera frames found. Check macOS Camera permission for Python.")
    else:
        print("Open the output images and choose the index showing Cisco Desk Camera 4K.")
        print("Then set MAYA_EXTERNAL_CAMERA_INDEX to that index in .env and restart Maya.")


def _probe(index: int, output_dir: Path) -> str:
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return f"index={index} open_ok=False"
    frame = None
    for _ in range(12):
        ok, candidate = cap.read()
        if ok and candidate is not None:
            frame = candidate
            break
        time.sleep(0.2)
    cap.release()
    if frame is None:
        return f"index={index} open_ok=True read_ok=False"
    path = output_dir / f"camera_index_{index}.jpg"
    cv2.imwrite(str(path), frame)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return (
        f"index={index} open_ok=True read_ok=True "
        f"shape={tuple(frame.shape)} mean_brightness={gray.mean():.2f} "
        f"saved={path}"
    )


if __name__ == "__main__":
    main()
