from __future__ import annotations

from word_section_repair import strengthen_word_sections


def main() -> None:
    router_sections = [
        ("Purpose", ["Router setup guide."]),
        ("Configuration Steps", ["Connect the modem to the WAN port.", "Open the router admin interface."]),
        ("Safety Notes", ["Configuration Backups", "Firmware Risks"]),
    ]
    repaired = strengthen_word_sections("make router setup guide in Word", router_sections)
    text = "\n".join(line for _, lines in repaired for line in lines).lower()
    _require("admin password" in text, "router repair missing admin password")
    _require("wifi password" in text, "router repair missing WiFi password")
    _require("ssid" in text, "router repair missing SSID")
    _require("wpa2" in text or "wpa3" in text, "router repair missing WPA security")
    _require("firmware risks: do not interrupt" in text, "empty firmware label was not repaired")

    proposal_sections = [
        ("Scope", ["In Scope", "Document quality checks", "Out of Scope"]),
        ("Recommended Approach", ["The Three Tier Review Process", "Tier 1: local QA.", "Tier 2: peer review."]),
        ("Next Steps", ["Approve the pilot.", "***"]),
    ]
    repaired = strengthen_word_sections("proposal for Kampung AI document quality", proposal_sections)
    text = "\n".join(line for _, lines in repaired for line in lines).lower()
    _require("out of scope:" in text, "proposal repair missing Out of Scope content")
    _require("tier 3" in text, "proposal repair missing Tier 3")
    _require("***" not in text, "proposal repair did not remove markdown divider")
    print("word_section_repair_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
