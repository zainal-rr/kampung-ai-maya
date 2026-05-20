from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from file_actions import FileActionRouter
from permission_policy import action_permission, contains_sensitive_info, is_private_exposure


async def main() -> None:
    _require(action_permission("write_file") == "allow", "write_file should be allowed")
    _require(action_permission("create_file") == "allow", "create_file should be allowed")
    _require(action_permission("browse_web") == "allow", "browse_web should be allowed")
    _require(action_permission("browser_click") == "allow", "browser_click should be allowed")
    _require(action_permission("travel_search") == "allow", "travel_search should be allowed")
    _require(action_permission("edit_document") == "allow", "edit_document should be allowed")
    _require(action_permission("edit_presentation") == "allow", "edit_presentation should be allowed")
    _require(action_permission("network_check") == "allow", "network_check should be allowed")
    _require(action_permission("cloudflare_use") == "allow", "Cloudflare use should be allowed")
    _require(action_permission("gcp_use") == "allow", "GCP use should be allowed")
    _require(action_permission("delete_file") == "confirm", "delete_file should need confirmation")
    _require(action_permission("send_message") == "confirm", "send_message should need confirmation")
    _require(action_permission("sensitive_browser_click") == "confirm", "sensitive_browser_click should need confirmation")
    _require(action_permission("book_travel") == "confirm", "book_travel should need confirmation")
    _require(action_permission("purchase_item") == "confirm", "purchase_item should need confirmation")
    _require(action_permission("make_payment") == "confirm", "make_payment should need confirmation")
    _require(contains_sensitive_info("my password is abc"), "password marker was missed")
    _require(is_private_exposure("show my bank account"), "private exposure was not blocked")
    _require(not is_private_exposure("do not show my password"), "safety rule was mistaken for exposure")
    await _file_write_checks()
    print("permission_policy_smoke: ok")


async def _file_write_checks() -> None:
    router = FileActionRouter()
    with tempfile.TemporaryDirectory(prefix="maya-file-action-") as tmp:
        target = Path(tmp) / "note.txt"
        created = await router.handle(f"create file {target} with hello", "telegram")
        _require("wrote" in created.lower() and target.read_text() == "hello", "file was not created")
        blocked = await router.handle(f"create file {target} with again", "telegram")
        _require("already exists" in blocked, "create should not overwrite")
        written = await router.handle(f"write file {target} with updated", "telegram")
        _require("wrote" in written.lower() and target.read_text() == "updated", "file was not written")
        denied = await router.handle(f"write file {target} with my password is abc", "telegram")
        _require("sensitive private" in denied.lower(), "sensitive content was not blocked")
        default_path = router._resolve_path("maya-note.txt")
        _require(default_path == Path.home() / "Downloads" / "maya-note.txt", "relative files should default to Downloads")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
