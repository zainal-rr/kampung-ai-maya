from __future__ import annotations

from weather_lookup import detect_weather_location, is_weather_question


def main() -> None:
    _require(is_weather_question("what is the weather in Kuala Lumpur today?"), "weather question missed")
    _require(is_weather_question("temperature in KL"), "temperature question missed")
    _require(not is_weather_question("what can you do today"), "false weather question")
    kl = detect_weather_location("what is the weather in Kuala Lumpur today?")
    _require(kl is not None and kl.name == "Kuala Lumpur", "Kuala Lumpur was not detected")
    short = detect_weather_location("temperature in KL")
    _require(short is not None and short.name == "Kuala Lumpur", "KL alias was not detected")
    unknown = detect_weather_location("weather in Atlantis")
    _require(unknown is None, "unknown location should not resolve")
    print("weather_lookup_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
