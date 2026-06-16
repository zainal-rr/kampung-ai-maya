from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScreenSnapshot:
    visible: bool
    status: str
    image_bytes: bytes | None = None


class MacScreenService:
    def capture_once(self) -> ScreenSnapshot:
        fd, filename = tempfile.mkstemp(prefix="maya-screen-", suffix=".jpg")
        os.close(fd)
        path = Path(filename)
        try:
            result = subprocess.run(
                ["screencapture", "-x", "-t", "jpg", str(path)],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "screen capture failed").strip()
                return ScreenSnapshot(False, _permission_hint(detail))
            data = path.read_bytes()
            if not data:
                return ScreenSnapshot(False, "Screen capture returned an empty image.")
            return ScreenSnapshot(True, "screen visible", data)
        except FileNotFoundError:
            return ScreenSnapshot(False, "macOS screencapture is unavailable.")
        except subprocess.TimeoutExpired:
            return ScreenSnapshot(False, "Screen capture timed out.")
        finally:
            path.unlink(missing_ok=True)


def _permission_hint(detail: str) -> str:
    lowered = detail.lower()
    if "not authorized" in lowered or "permission" in lowered or "denied" in lowered:
        return "Screen Recording permission is blocked for this runtime."
    return detail
