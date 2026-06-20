from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class WeatherPoint:
    name: str
    latitude: float
    longitude: float
    timezone: str


KNOWN_LOCATIONS = {
    "kuala lumpur": WeatherPoint("Kuala Lumpur", 3.139, 101.6869, "Asia/Kuala_Lumpur"),
    "kl": WeatherPoint("Kuala Lumpur", 3.139, 101.6869, "Asia/Kuala_Lumpur"),
    "penang": WeatherPoint("Penang", 5.4141, 100.3288, "Asia/Kuala_Lumpur"),
    "george town": WeatherPoint("George Town", 5.4141, 100.3288, "Asia/Kuala_Lumpur"),
    "singapore": WeatherPoint("Singapore", 1.3521, 103.8198, "Asia/Singapore"),
}


def is_weather_question(text: str) -> bool:
    lowered = text.lower()
    return "weather" in lowered or "temperature" in lowered or "forecast" in lowered


def detect_weather_location(text: str) -> WeatherPoint | None:
    lowered = text.lower()
    for marker, point in KNOWN_LOCATIONS.items():
        if marker in lowered:
            return point
    return None


async def current_weather_summary(text: str) -> str | None:
    point = detect_weather_location(text)
    if point is None:
        return None
    params = {
        "latitude": point.latitude,
        "longitude": point.longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
        "timezone": point.timezone,
    }
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        response.raise_for_status()
    data = response.json()
    current = data.get("current") or {}
    temp = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    rain = current.get("precipitation")
    wind = current.get("wind_speed_10m")
    code = _weather_code_text(current.get("weather_code"))
    time = current.get("time", "current local time")
    return (
        f"Weather data for {point.name} at {time}: "
        f"{temp} C, {code}, humidity {humidity} percent, "
        f"rain {rain} mm, wind {wind} km/h."
    )


def _weather_code_text(code: object) -> str:
    mapping = {
        0: "clear",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "rime fog",
        51: "light drizzle",
        53: "drizzle",
        55: "heavy drizzle",
        61: "light rain",
        63: "rain",
        65: "heavy rain",
        80: "light showers",
        81: "showers",
        82: "heavy showers",
        95: "thunderstorm",
    }
    try:
        return mapping.get(int(code), "conditions code unavailable")
    except (TypeError, ValueError):
        return "conditions unavailable"
