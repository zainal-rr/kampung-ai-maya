from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from file_actions import FileActionRouter
from permission_policy import action_permission, contains_sensitive_info, is_private_exposure, path_needs_confirmation
from workspace_paths import workspace_dir


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
    _require(not contains_sensitive_info("create a password field in the document"), "password documentation was over-blocked")
    _require(not contains_sensitive_info("Password: choose at least 12 characters and one symbol."), "password guidance was over-blocked")
    _require(not contains_sensitive_info("Password: minimum 12 characters and one symbol."), "password policy field text was over-blocked")
    _require(not contains_sensitive_info("Password: required field on the signup form."), "password field documentation was over-blocked")
    _require(not contains_sensitive_info("The password is required for account creation."), "password-is documentation was over-blocked")
    _require(contains_sensitive_info("my password is abcdefghij123"), "password secret format was missed")
    _require(contains_sensitive_info("the password is hunter2 for github"), "password-is secret cue was missed")
    _require(contains_sensitive_info("password = hunter2"), "password assignment was missed")
    _require(contains_sensitive_info("password: hunter2 for github"), "password assignment with context was missed")
    _require(is_private_exposure("show sk-abcdefghijklmnopqrstuvwxyz123456"), "private exposure was not blocked")
    _require(not is_private_exposure("do not show my password"), "safety rule was mistaken for exposure")
    _require(path_needs_confirmation(Path.home() / ".ssh" / "config"), "SSH config should need confirmation")
    _require(
        path_needs_confirmation(Path.home() / "Library" / "LaunchAgents" / "x.plist"),
        "LaunchAgents should need confirmation",
    )
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
        denied = await router.handle(f"write file {target} with sk-abcdefghijklmnopqrstuvwxyz123456", "telegram")
        _require("sensitive private" in denied.lower(), "sensitive content was not blocked")
        sensitive = await router.handle("write file ~/.zshrc with export MAYA=1", "telegram")
        _require("can't write" in sensitive.lower() and "protected" in sensitive.lower(), "sensitive path was not gated")
        default_path = router._resolve_path("maya-note.txt")
        _require(default_path == workspace_dir("") / "maya-note.txt", "relative files should default to Desktop Maya")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
