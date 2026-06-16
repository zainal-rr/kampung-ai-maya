from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


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
