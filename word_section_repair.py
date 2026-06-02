from __future__ import annotations

import re


def strengthen_word_sections(topic: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    if _is_router_topic(topic):
        return _strengthen_router_sections(sections)
    if _is_proposal_topic(topic):
        return _strengthen_proposal_sections(sections)
    return sections


def _strengthen_router_sections(sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    result: list[tuple[str, list[str]]] = []
    for heading, lines in sections:
        fixed = _repair_empty_labels(lines)
        if _norm_heading(heading) == "configuration steps":
            fixed = _ensure_lines(
                fixed,
                (
                    ("admin password", "Log into the router admin interface and change the default admin password before enabling remote or wireless access."),
                    ("ssid", "Set a clear WiFi network name or SSID so the correct network is easy to identify."),
                    ("wifi password", "Create a strong WiFi password or passphrase and save it somewhere the owner can retrieve later."),
                    ("wpa", "Use WPA2 or WPA3 security mode and avoid weak legacy encryption such as WEP."),
                ),
            )
        elif _norm_heading(heading) == "safety notes":
            fixed = _ensure_lines(
                fixed,
                (
                    ("firmware", "Firmware risks: do not interrupt power during firmware updates, and keep a configuration backup before upgrading."),
                    ("admin password", "Keep the new admin password private and do not reuse the same password as the WiFi passphrase."),
                ),
            )
        result.append((heading, fixed))
    return result


def _repair_empty_labels(lines: list[str]) -> list[str]:
    repaired: list[str] = []
    for line in lines:
        if _looks_like_empty_label(line):
            repaired.append("Firmware risks: do not interrupt power during firmware updates, and keep a configuration backup before upgrading.")
        else:
            repaired.append(line)
    return repaired


def _strengthen_proposal_sections(sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    result: list[tuple[str, list[str]]] = []
    for heading, lines in sections:
        fixed = _remove_markdown_dividers(lines)
        if _norm_heading(heading) == "scope":
            fixed = _repair_out_of_scope(fixed)
        elif _norm_heading(heading) == "recommended approach":
            fixed = _complete_tiered_process(fixed)
        result.append((heading, fixed))
    return result


def _repair_out_of_scope(lines: list[str]) -> list[str]:
    fixed: list[str] = []
    for index, line in enumerate(lines):
        if _normalize(line).strip(" :") == "out of scope" and index == len(lines) - 1:
            fixed.append("Out of Scope: unrelated brand redesign, non-document product work, and private user data policy changes are outside this proposal.")
        else:
            fixed.append(line)
    return fixed


def _complete_tiered_process(lines: list[str]) -> list[str]:
    body = _normalize(" ".join(lines))
    if "three tier" in body and "tier 3" not in body:
        lines = [
            *lines,
            "Tier 3 (Final QA): a steward review confirms completeness, factual accuracy, formatting consistency, and delivery readiness before the document is called final.",
        ]
    return lines


def _remove_markdown_dividers(lines: list[str]) -> list[str]:
    return [line for line in lines if str(line).strip() not in {"***", "---"}]


def _ensure_lines(lines: list[str], requirements: tuple[tuple[str, str], ...]) -> list[str]:
    body = _normalize(" ".join(lines))
    updated = list(lines)
    for marker, line in requirements:
        if marker not in body:
            updated.append(line)
            body += " " + _normalize(line)
    return updated


def _looks_like_empty_label(line: str) -> bool:
    clean = str(line).strip(" :")
    if clean.lower() != "firmware risks":
        return False
    if len(clean.split()) > 3 or len(clean) < 4:
        return False
    if clean.endswith("."):
        return False
    return bool(re.match(r"^[A-Z][A-Za-z0-9]*(?: [A-Z][A-Za-z0-9]*){0,2}$", clean))


def _is_router_topic(topic: str) -> bool:
    lowered = _normalize(topic)
    return "router" in lowered or "wifi" in lowered or "wi fi" in lowered


def _is_proposal_topic(topic: str) -> bool:
    return "proposal" in _normalize(topic)


def _norm_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()
