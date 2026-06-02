from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlightDetails:
    origin: str
    destination: str
    depart: str
    return_date: str = ""
    one_way: bool = True
    missing: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class FieldAttempt:
    field: str
    value: str
    status: str
    detail: str = ""

    def line(self) -> str:
        suffix = f" ({self.detail})" if self.detail else ""
        return f"{self.field}: {self.status} {self.value}{suffix}".strip()


MONTHS = {
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}


KNOWN_DESTINATIONS = (
    "Penang", "Langkawi", "Kota Kinabalu", "Kuching", "Johor Bahru",
    "Kuala Terengganu", "Kuantan", "Ipoh", "Malacca", "Melaka",
    "Singapore", "Bangkok", "Tokyo", "Osaka", "Kyoto", "Seoul", "Taipei", "Hong Kong",
)
