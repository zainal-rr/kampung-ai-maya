from __future__ import annotations

import asyncio
import re
from pathlib import Path

from permission_policy import action_permission, hard_no_private_exposure_text, path_allowed, path_needs_confirmation
from workspace_paths import workspace_dir


KNOWN_HOME_DIRS = {
    "desktop": "Desktop",
    "documents": "Documents",
    "downloads": "Downloads",
}


class FileActionRouter:
    async def handle(self, text: str, channel: str) -> str | None:
        request = self._parse(text)
        if request is None:
            return None
        action, raw_path, content = request
        if action_permission("write_file", content) == "deny":
            return hard_no_private_exposure_text()

        path = self._resolve_path(raw_path)
        if path_needs_confirmation(path):
            return f"That path is sensitive. Confirm before I write to {path}."
        if not path_allowed(path):
            return f"I can't write to {path}."
        if action == "create" and path.exists():
            return f"{path} already exists. Say write file if you want me to replace it."

        try:
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(path.write_text, content, "utf-8")
        except Exception as exc:
            return f"I couldn't write that file: {exc}"
        reply = f"Done. I wrote {path}."
        if channel == "telegram":
            reply += f"\n[file:{path}]"
        return reply

    @staticmethod
    def _parse(text: str) -> tuple[str, str, str] | None:
        match = re.match(r"^(create|write)(?: a)? file\s+(.+?)\s+with\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return None
        return match.group(1).lower(), match.group(2).strip(), match.group(3).strip()

    @staticmethod
    def _resolve_path(raw_path: str) -> Path:
        cleaned = raw_path.strip().strip("\"'")
        desktop_match = re.match(r"^(?:on\s+)?desktop(?:\s+called)?\s+(.+)$", cleaned, re.IGNORECASE)
        if desktop_match:
            return Path.home() / "Desktop" / desktop_match.group(1).strip()
        path = Path(cleaned).expanduser()
        if path.is_absolute():
            return path
        parts = path.parts
        if parts and parts[0].lower() in KNOWN_HOME_DIRS:
            return Path.home() / KNOWN_HOME_DIRS[parts[0].lower()] / Path(*parts[1:])
        return workspace_dir("") / path
