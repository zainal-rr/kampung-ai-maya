from __future__ import annotations

from document_actions_context import *


def _word_repair_request(topic: str, issues: str, current: str) -> str:
    return (
        "Repair this Word document and return a complete corrected Markdown draft.\n"
        f"Original user request: {topic}\n"
        f"QA issues to fix: {issues}\n\n"
        f"Scenario-specific Word standard:\n{word_prompt_context(topic)}\n\n"
        "Rules:\n"
        "1) Keep the same document purpose and scenario.\n"
        "2) Fill every required section with concrete content.\n"
        "3) Remove empty labels, raw markdown dividers, placeholders, and incomplete tier/step frameworks.\n"
        "4) Use topic-specific details, not meta commentary about what each section should contain.\n"
        "5) Return the full corrected document, not a patch note.\n\n"
        f"Current extracted document:\n{current[:6000]}"
    )


def _document_edit_request(text: str) -> tuple[str, bool] | None:
    cleaned = " ".join(str(text).strip().split())
    slash = re.match(r"^/edit(?:\s+(.+))?$", cleaned, re.I)
    if slash:
        instruction = (slash.group(1) or "").strip(" .")
        return (instruction or "make the latest file better according to the current context", False)
    cleaned = re.sub(r"^(?:maya\s+|please\s+|can you\s+|could you\s+|would you\s+|help me\s+)+", "", cleaned, flags=re.I).strip()
    save_copy = bool(re.search(r"\b(?:new version|new copy|create a copy|make a copy|save a copy|copy|duplicate|don't overwrite|do not overwrite|without overwriting)\b", cleaned, re.I))
    copy_match = re.match(
        r"^(?:make|create|save)\s+(?:a\s+)?(?:new\s+version|new\s+copy|copy|duplicate)\s+(?:of\s+)?"
        r"(?:that|it|this|the\s+last\s+(?:document|doc|file)|the\s+(?:document|doc|file))\s*"
        r"(?:to|into|with|so\s+that)?\s*(.+)$",
        cleaned,
        re.I,
    )
    if copy_match and copy_match.group(1).strip():
        return copy_match.group(1).strip(" ."), True
    cleaned = re.sub(r"\b(?:as\s+a\s+)?(?:new version|new copy|create a copy|make a copy|save a copy|copy|duplicate|don't overwrite|do not overwrite|without overwriting)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"^(?:and|then)\s+", "", " ".join(cleaned.split()), flags=re.I)
    if _looks_like_text_transform(cleaned):
        return None
    patterns: tuple[tuple[str, bool], ...] = (
        (
            r"^(?:update|edit|revise|change|modify)\s+"
            r"(that\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|this\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|the\s+last\s+(?:document|doc|file)|the\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|that|it|this)\s*"
            r"(?:to|into|with|so\s+that)?\s*(.+)$",
            True,
        ),
        (
            r"^(?:make|turn)\s+"
            r"(that\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|this\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|the\s+last\s+(?:document|doc|file)|the\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|that|it|this)\s+"
            r"(?:into|a|an)?\s*(.+)$",
            True,
        ),
    )
    for pattern, requires_document_signal in patterns:
        match = re.match(pattern, cleaned, re.I)
        if match and match.group(2).strip():
            target = match.group(1)
            instruction = match.group(2).strip(" .")
            instruction = re.sub(r"^(?:a|an)\s+", "", instruction, flags=re.I)
            explicit_target = not re.fullmatch(r"that|it|this", target, re.I)
            if explicit_target or not requires_document_signal or _looks_like_document_edit_instruction(instruction):
                return instruction, save_copy
    return None


def _looks_like_text_transform(cleaned: str) -> bool:
    return bool(re.match(
        r"^(?:make|turn)\s+(?:that|it|this)\s+(?:into|a|an)\s+"
        r"(?:meeting minutes?|minutes?|email|message|slack note|note|summary|subject line|reply|response)\b",
        cleaned,
        re.I,
    ))


def _looks_like_document_edit_instruction(instruction: str) -> bool:
    lowered = " ".join(str(instruction).lower().split())
    return bool(
        re.search(r"\b\d{1,2}\s*[- ]?\s*(?:day|days|slides?|pages?|rows?|columns?)\b", lowered)
        or re.search(
            r"\b(?:add|append|remove|delete|include|insert|replace|rewrite|rename|reformat|format|"
            r"heading|title|section|chapter|slide|speaker notes?|presenter notes?|image|photo|chart|"
            r"table|sheet|worksheet|formula|budget|itinerary|recommendations?|config|putty|ssh|cli|"
            r"router|excel|spreadsheet|workbook|powerpoint|presentation|deck|word|document|doc|file)\b",
            lowered,
        )
    )


def _backup_word_file(path: Path) -> Path:
    backup_dir = path.parent / ".maya_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = versioned_path(backup_dir / f"{path.stem}-backup-v1{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def _edited_word_topic(path: Path, instruction: str, current: str) -> str:
    title = _document_title_from_text(current) or re.sub(r"-v\d+$", "", path.stem).replace("-", " ").title()
    if re.search(r"\b(?:putty|ssh|serial|console|cli|command|config)\b", instruction, re.I):
        if re.search(r"\brouter\b", f"{title} {instruction}", re.I):
            return "Router Setup Guide With PuTTY Config"
        return f"{title} With PuTTY Config"
    day_match = re.search(r"\b(\d{1,2})\s*[- ]?\s*(?:day|days)\b", instruction, re.I)
    if not day_match:
        return title
    days = int(day_match.group(1))
    cleaned_title = re.sub(r"^\d{1,2}\s*[- ]?\s*day\s+", "", title, flags=re.I).strip()
    return f"{days}-day {cleaned_title}"


def _document_title_from_text(text: str) -> str:
    for line in str(text).splitlines():
        clean = " ".join(line.split()).strip()
        if clean:
            return clean[:90]
    return ""


def _word_edit_request(topic: str, instruction: str, current: str) -> str:
    return (
        "Update this existing Word document and return the full revised Markdown draft.\n"
        f"Updated document topic: {topic}\n"
        f"User edit instruction: {instruction}\n\n"
        f"Scenario-specific Word standard:\n{word_prompt_context(topic)}\n\n"
        "Rules:\n"
        "1) Preserve useful existing details that still fit the new instruction.\n"
        "2) Apply the edit throughout the whole document, including headings, duration, recommendations, budget, and transit notes.\n"
        "3) If the duration changes, create exactly the required day-level sections and remove conflicting old duration claims.\n"
        "4) Return the full revised document, not a patch note.\n"
        "5) Use concrete topic-specific details, not placeholders or meta commentary.\n\n"
        "6) If the user asks what to write in PuTTY, include a clearly labeled sample command/config section with actual terminal lines, explain placeholders such as interface names and SSID/password, and avoid pretending the commands apply to every router brand without adaptation.\n\n"
        f"Current extracted document:\n{current[:7000]}"
    )


def _word_document_title(topic: str) -> str:
    title = topic.strip().title()
    replacements = {
        "Ai": "AI",
        "Api": "API",
        "Cli": "CLI",
        "Html": "HTML",
        "Imac": "iMac",
        "Pptx": "PPTX",
        "Putty": "PuTTY",
        "Wifi": "WiFi",
    }
    for wrong, right in replacements.items():
        title = re.sub(rf"\b{wrong}\b", right, title)
    return title or "Maya Word Document"


def _router_putty_topic(topic: str) -> bool:
    lowered = str(topic).lower()
    return "router" in lowered and any(marker in lowered for marker in ("putty", "ssh", "serial", "console", "cli", "command"))


def _router_putty_repair_markdown() -> str:
    return (
        "# Router Setup Guide With PuTTY Config\n\n"
        "## Purpose\n\n"
        "1) Configure a basic router through PuTTY using a simple example that shows what to type and what to replace.\n"
        "2) Treat the commands as a safe lab template. Confirm the actual router brand, interface names, and operating system before pasting anything.\n\n"
        "## Prerequisites\n\n"
        "1) PuTTY installed, serial console cable or SSH access, correct COM port or router management IP, and admin credentials for the router interface.\n"
        "2) Router details to confirm before typing: WAN interface name, LAN interface name, LAN subnet, WiFi SSID, WiFi password, and ISP requirements.\n"
        "3) Replace example values such as GigabitEthernet0/0, GigabitEthernet0/1, YOUR_SSID, YOUR_WIFI_PASSWORD, and 192.168.1.1 with the real values for your router.\n\n"
        "## Configuration Steps\n\n"
        "1) Open PuTTY. Use Serial with the detected COM port and 9600 baud, or use SSH to the router management IP if SSH is already enabled.\n"
        "2) Press Enter until the router prompt appears, then log in with the router admin credentials.\n"
        "3) Simple Cisco-style example to adapt before use:\n"
        "enable; configure terminal; hostname HomeRouter; enable secret CHANGE_ADMIN_PASSWORD; interface GigabitEthernet0/0; description WAN_TO_MODEM; ip address dhcp; no shutdown; interface GigabitEthernet0/1; description LAN_TO_HOME; ip address 192.168.1.1 255.255.255.0; no shutdown; ip dhcp pool HOME_LAN; network 192.168.1.0 255.255.255.0; default-router 192.168.1.1; dns-server 1.1.1.1 8.8.8.8; wlan ssid YOUR_SSID; wpa2 psk YOUR_WIFI_PASSWORD; end; show running-config; write memory.\n"
        "4) If your router supports a different command style, such as MikroTik, Juniper, TP-Link, UniFi, or ISP firmware, use the same intent but translate the syntax instead of pasting this directly.\n\n"
        "## Verification\n\n"
        "1) Run show ip interface brief to confirm WAN and LAN interfaces are up.\n"
        "2) Run show running-config to confirm the hostname, interface IPs, DHCP pool, SSID, security mode, and saved settings look correct.\n"
        "3) Run ping 8.8.8.8 and ping google.com to verify internet reachability and DNS.\n"
        "4) Join the WiFi network from a phone or laptop and confirm the WiFi password works.\n\n"
        "## Troubleshooting\n\n"
        "1) If PuTTY shows unreadable characters, close the session and retry with 115200 baud instead of 9600.\n"
        "2) If login fails, confirm the admin username, admin password, and whether console login is disabled by the router vendor.\n"
        "3) If WAN does not receive an address, check modem bridge mode, ISP VLAN or PPPoE requirements, and the actual WAN interface name.\n"
        "4) If WiFi does not appear, confirm the wireless radio is enabled and that the router supports CLI wireless configuration.\n\n"
        "## Safety Notes\n\n"
        "1) Do not run write memory until the current session has been verified and you can still reach the router.\n"
        "2) Keep a backup or screenshot of the old admin, WAN, LAN, and WiFi settings before changing them.\n"
        "3) Do not share the admin password, WiFi password, or full running configuration in public channels.\n"
        "4) Keep firmware updates separate from first-time configuration so a failed firmware update does not get mixed with setup troubleshooting.\n\n"
        "## Next Steps\n\n"
        "1) Save a sanitized copy of the final configuration without passwords.\n"
        "2) Create a guest WiFi network if the router supports it.\n"
        "3) Review connected devices after setup and rename known devices so unknown clients are easier to spot later.\n"
    )
