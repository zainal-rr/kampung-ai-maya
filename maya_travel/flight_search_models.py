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


# Google Flights resolves city names to airport cities/codes on results pages
# (e.g. Penang -> "George Town" and "KUL-PEN"), so option matching needs aliases.
DESTINATION_ALIASES = {
    "penang": ("pen", "george town"),
    "langkawi": ("lgk",),
    "kota kinabalu": ("bki",),
    "kuching": ("kch",),
    "johor bahru": ("jhb", "senai"),
    "kuala terengganu": ("tgg",),
    "kuantan": ("kua",),
    "ipoh": ("iph",),
    "malacca": ("mkz",),
    "melaka": ("mkz",),
    "singapore": ("sin", "changi"),
    "bangkok": ("bkk", "dmk", "suvarnabhumi", "don mueang"),
    "tokyo": ("nrt", "hnd", "narita", "haneda"),
    "osaka": ("kix", "itm", "kansai"),
    "kyoto": ("kix", "osaka", "kansai"),
    "seoul": ("icn", "gmp", "incheon"),
    "taipei": ("tpe", "taoyuan"),
    "hong kong": ("hkg",),
    "kuala lumpur": ("kul",),
}


def destination_match_tokens(destination: str) -> tuple[str, ...]:
    key = destination.lower().strip()
    return (key, *DESTINATION_ALIASES.get(key, ()))
