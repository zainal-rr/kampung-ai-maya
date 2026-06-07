from assistant_command_helpers import confirmation_decision


def main() -> None:
    _require(confirmation_decision("yes") == "approve", "plain yes should approve")
    _require(confirmation_decision("okay") == "approve", "plain okay should approve")
    _require(confirmation_decision("okay cakap malay") is None, "language request should not approve")
    _require(confirmation_decision("okay wait what is quantum computing") is None, "question should not approve")
    _require(confirmation_decision("okay wait change it to two person now") is None, "edit request should not approve")
    print("confirmation_decision_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
