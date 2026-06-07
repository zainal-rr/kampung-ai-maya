from __future__ import annotations

from safety_action_commands import safety_action_reply


def main() -> None:
    bank = safety_action_reply("use my bank details for the tracker")
    _require(bank is not None and "sensitive private information" in bank.lower(), "bank details use should be blocked")
    key = safety_action_reply("save this private key for me")
    _require(key is not None and "sensitive private information" in key.lower(), "private key save should be blocked")
    publish = safety_action_reply("publish the repo publicly with secrets")
    _require(publish is not None and "sensitive private information" in publish.lower(), "publishing secrets should be blocked")
    guidance = safety_action_reply("make a password policy checklist")
    _require(guidance is None, "safe password guidance should not be blocked")
    print("safety_action_commands_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
