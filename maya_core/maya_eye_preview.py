from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from maya_core.maya_eye_overlay import clear_preview_target, draw_preview_targets
from maya_core.vision_blocked import frame_blocked


def pid_file() -> Path:
    return Path(os.getenv("MAYA_EYE_PREVIEW_PID_FILE", "/tmp/maya-eye-preview.pid"))


def start_preview() -> str:
    if os.getenv("MAYA_EYE_PREVIEW", "0") != "1":
        return "Local camera preview is disabled."
    if _pid_alive(_read_pid()):
        return "Local camera preview is already open on the iMac."
    command = [sys.executable, str(Path(__file__).resolve()), "--run-preview"]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return f"I could not open the local camera preview: {exc}"
    time.sleep(0.5)
    if process.poll() is not None:
        pid_file().unlink(missing_ok=True)
        return (
            "I could not open the local camera preview. "
            "Check Camera permission for the runtime that launched Maya."
        )
    pid_file().write_text(str(process.pid), encoding="utf-8")
    return "Local camera preview is open on the iMac."


def stop_preview() -> None:
    pid = _read_pid()
    if pid and _pid_alive(pid):
        try:
            os.kill(pid, 15)
        except OSError:
            pass
        for _ in range(10):
            if not _pid_alive(pid):
                break
            time.sleep(0.1)
        if _pid_alive(pid):
            try:
                os.kill(pid, 9)
            except OSError:
                pass
    pid_file().unlink(missing_ok=True)
    clear_preview_target()


def preview_status() -> str:
    if os.getenv("MAYA_EYE_PREVIEW", "0") != "1":
        return "disabled"
    return "open" if _pid_alive(_read_pid()) else "closed"


def run_preview() -> int:
    try:
        import cv2
    except ModuleNotFoundError:
        return 2

    index = int(os.getenv("MAYA_EXTERNAL_CAMERA_INDEX", "0"))
    title = os.getenv("MAYA_EYE_PREVIEW_TITLE", "Maya Eye")
    close_frames = int(os.getenv("MAYA_EYE_BLOCKED_CLOSE_FRAMES", "30"))
    blocked_frames = 0
    trackers = {}
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return 2
    try:
        cv2.namedWindow(title, cv2.WINDOW_NORMAL)
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                blocked_frames += 1
                if blocked_frames >= close_frames:
                    break
                time.sleep(0.1)
                continue
            if frame_blocked(frame):
                blocked_frames += 1
                if blocked_frames >= close_frames:
                    break
            else:
                blocked_frames = 0
                draw_preview_targets(frame, trackers)
            cv2.imshow(title, frame)
            key = cv2.waitKey(30) & 0xFF
            if key in {27, ord("q")} or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        pid_file().unlink(missing_ok=True)
        clear_preview_target()
    return 0


def _read_pid() -> int | None:
    try:
        return int(pid_file().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-preview", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run_preview() if args.run_preview else 0)
