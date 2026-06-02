from __future__ import annotations

from hardware_live_proof import format_hardware_live_proof, hardware_live_proof_items


def main() -> None:
    items = hardware_live_proof_items()
    text = format_hardware_live_proof()
    _require(any(item.name == "Mudra adapter prepared" and item.status == "pass" for item in items), "Mudra adapter not prepared")
    _require(any(item.name == "Omi adapter prepared" and item.status == "pass" for item in items), "Omi adapter not prepared")
    _require("manual-live-required" in text, "manual live requirement not explicit")
    _require("prepared adapters are not live proof" in text, "proof boundary missing")
    print("hardware_live_proof_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
