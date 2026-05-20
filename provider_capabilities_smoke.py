from __future__ import annotations

from provider_capabilities import CAPABILITIES, capability_context, review_triggers


def main() -> None:
    required = {"sight", "mind", "steward", "artisan", "pulse"}
    _require(required.issubset(CAPABILITIES), "missing provider capabilities")
    _require(CAPABILITIES["sight"].can_write_memory, "Gemini should own memory first pass")
    _require(not CAPABILITIES["steward"].can_write_memory, "Claude should review, not write memory")
    _require(CAPABILITIES["artisan"].owner == "The Artisan", "Kimi owner wrong")
    _require("/complex" in CAPABILITIES["mind"].triggers, "GPT complex trigger missing")
    _require("review" in review_triggers(), "Claude review trigger missing")
    context = capability_context()
    _require("The Steward" in context and "The Sight" in context, "capability context incomplete")
    print("provider_capabilities_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
