from __future__ import annotations

import re
from dataclasses import dataclass

from frequent_sites_catalog import FREQUENT_SITES, FrequentSite, FrequentSiteMatch


def find_frequent_site_request(text: str) -> FrequentSiteMatch | None:
    lowered = _normalize_text(text)
    best: tuple[int, FrequentSite, str] | None = None
    for site in FREQUENT_SITES:
        terms = (site.domain, site.name, *site.aliases)
        for term in terms:
            if _term_present(lowered, term):
                score = len(_normalize_text(term))
                if best is None or score > best[0]:
                    best = (score, site, term)
    if best is None:
        return None
    return FrequentSiteMatch(site=best[1], reason=f"frequent site matched {best[1].name}")


def frequent_site_catalog() -> list[dict[str, str]]:
    return [
        {
            "id": site.id,
            "name": site.name,
            "domain": site.domain,
            "category": site.category,
            "child_skill": site.child_skill,
            "policy": site.policy,
        }
        for site in FREQUENT_SITES
    ]


def should_use_specialized_site_skill(text: str, site: FrequentSite) -> bool:
    lowered = _normalize_text(text)
    if site.child_skill == "airbnb_stay_search":
        return any(word in lowered for word in ("find", "search", "look", "stay", "listing", "price", "guest", "home", "house", "airbnb in"))
    if site.child_skill == "booking_com_hotel_search":
        return any(word in lowered for word in ("find", "search", "look", "hotel", "room", "accommodation", "price", "stay", "booking.com in"))
    return False


def is_sensitive_frequent_site(site: FrequentSite) -> bool:
    return site.category in {"sensitive_finance", "communication_sensitive"} or "sensitive" in site.child_skill


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _term_present(text: str, term: str) -> bool:
    term = _normalize_text(term)
    if not term:
        return False
    if "." in term or term.startswith("127"):
        return term in text
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))
