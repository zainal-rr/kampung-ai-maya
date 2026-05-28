from __future__ import annotations

from language_policy import language_instruction, uses_malay_or_manglish, wants_malay_or_manglish


def main() -> None:
    english = "Why are you answering in manglish when I ask in English?"
    malay = "boleh bagitau apa benda ni?"
    request = "can you reply in malay?"
    mixed_request = "Maya cakap in malay please"

    _require(not uses_malay_or_manglish(english), "English complaint should not count as Manglish")
    _require("English only" in language_instruction(english), "English prompt should force English")
    _require(uses_malay_or_manglish(malay), "Malay/Manglish prompt was not detected")
    _require("Malay or Manglish" in language_instruction(malay), "Malay prompt should allow Malay/Manglish")
    _require(wants_malay_or_manglish(request), "Explicit Malay request was not detected")
    _require(wants_malay_or_manglish(mixed_request), "Mixed Malay request was not detected")

    print("language_policy_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
