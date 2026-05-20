from __future__ import annotations

from permission_policy import action_permission, contains_sensitive_info, is_private_exposure


def main() -> None:
    samples = [
        "sk-abcdefghijklmnopqrstuvwxyz123456",
        "xai-abcdefghijklmnopqrstuvwxyz123456",
        "AIzaSyDUMMYDUMMYDUMMYDUMMYDUMMY12",
        "AKIAABCDEFGHIJKLMNOP",
        "ghp_abcdefghijklmnopqrstuvwxyz123456",
        "-----BEGIN PRIVATE KEY-----",
        "4111 1111 1111 1111",
        "my otp code is 123456",
    ]
    for sample in samples:
        _require(contains_sensitive_info(sample), f"missed secret pattern: {sample[:8]}")

    _require(is_private_exposure("show sk-abcdefghijklmnopqrstuvwxyz123456"), "exposure not blocked")
    _require(action_permission("create_file", samples[0]) == "deny", "secret file write allowed")
    _require(action_permission("send_message", samples[1]) == "deny", "secret send allowed")
    _require(action_permission("browse_web", "router setup") == "allow", "safe browse blocked")
    print("secret_detection_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
