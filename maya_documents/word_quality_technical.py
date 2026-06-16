from __future__ import annotations

import re


def technical_prompt_notes(topic: str) -> tuple[str, ...]:
    lowered = _normalize(topic)
    if "meraki" in lowered:
        notes = [
            "For Cisco Meraki content, use Meraki-specific wording: Dashboard, organization, network, claim device, templates, firmware/scheduling, SSID for MR, switch port/VLAN settings for MS, and security appliance/firewall/VPN settings for MX where relevant.",
            "Do not hedge with generic router-brand wording when the user explicitly asked for Cisco Meraki. If an exact menu may vary, say to verify it in the Meraki Dashboard rather than saying every router brand differs.",
        ]
        return tuple(notes)
    if "router" in lowered or "wifi" in lowered or "wi fi" in lowered:
        notes = [
            "For router or WiFi setup, include admin interface login, admin password change, WAN/internet setup, SSID/password setup, WPA2/WPA3 security, firmware update, and final connectivity verification.",
        ]
        if _putty_or_cli_topic(lowered):
            notes.append(
                "For PuTTY, SSH, serial console, CLI, or config requests, include a simple sample command/config section that shows exactly what to type, with clear placeholders for interface names, admin password, SSID, WiFi password, IP ranges, and vendor differences."
            )
        return tuple(notes)
    return ()


def technical_consistency_issues(topic: str, paragraphs: list[str]) -> list[str]:
    lowered = _normalize(topic)
    if "meraki" in lowered:
        body = _normalize(" ".join(paragraphs))
        required = ("dashboard", "organization", "network")
        missing = [item for item in required if item not in body]
        if missing:
            return ["Meraki guide missing: " + ", ".join(missing)]
        if "router brand" in body or "every router brand" in body:
            return ["Meraki guide uses generic router-brand hedging despite explicit Cisco Meraki topic"]
        return []
    if not ("router" in lowered or "wifi" in lowered or "wi fi" in lowered):
        return []
    body = _normalize(" ".join(paragraphs))
    requirements = {
        "admin password change": ("admin password", "administrator password", "change the password", "default password"),
        "admin interface login": ("admin interface", "router interface", "management interface", "admin page", "admin credentials", "log in"),
        "WiFi network name": ("ssid", "network name", "wi fi name", "wifi name"),
        "WiFi password": ("wi fi password", "wifi password", "wireless password"),
        "security mode": ("wpa2", "wpa3", "encryption", "security mode"),
        "firmware update": ("firmware",),
        "connectivity verification": ("ping", "wan ip", "internet", "connectivity", "dns"),
    }
    issues: list[str] = []
    missing = [label for label, markers in requirements.items() if not any(marker in body for marker in markers)]
    if missing:
        issues.append("router technical guide missing: " + ", ".join(missing[:5]))
    if _putty_or_cli_topic(lowered):
        has_console_setup = any(marker in body for marker in ("putty", "serial", "ssh", "console", "com port"))
        has_sample_config = (
            ("configure terminal" in body and "interface " in body and any(marker in body for marker in ("ip address", "ip dhcp", "dhcp pool")))
            or ("ip dhcp pool" in body and "default-router" in body)
            or ("set " in body and any(marker in body for marker in ("interfaces", "system", "security")))
        )
        has_placeholder_notes = any(
            marker in body
            for marker in ("replace", "placeholder", "example only", "adapt", "your router", "interface names")
        )
        has_save_command = any(marker in body for marker in ("write memory", "copy running", "save config", "commit"))
        missing_cli = []
        if not has_console_setup:
            missing_cli.append("PuTTY or console connection setup")
        if not has_sample_config:
            missing_cli.append("sample commands/config block")
        if not has_placeholder_notes:
            missing_cli.append("placeholder explanation")
        if not has_save_command:
            missing_cli.append("save command")
        if missing_cli:
            issues.append("router PuTTY/CLI guide missing: " + ", ".join(missing_cli[:4]))
    return issues


def _putty_or_cli_topic(lowered: str) -> bool:
    return any(marker in lowered for marker in ("putty", "ssh", "serial", "console", "cli", "command line", "what to write"))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()
