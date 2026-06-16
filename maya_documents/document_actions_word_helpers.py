from __future__ import annotations

from document_actions_context import *
from document_actions_word_repair_templates import _router_putty_repair_markdown


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


def _generic_technical_troubleshooting_topic(topic: str) -> bool:
    lowered = re.sub(r"\s+", " ", str(topic).lower()).strip()
    if any(marker in lowered for marker in ("router", "wifi", "wi fi", "wireless", "putty", "ssh", "serial", "console", "cli")):
        return False
    return bool(
        re.search(r"\btechnical\s+troubleshooting\s+guide\b", lowered)
        or re.search(r"\btroubleshooting\s+guide\b", lowered)
    )


def _generic_technical_troubleshooting_repair_markdown() -> str:
    return (
        "# Technical Troubleshooting Guide\n\n"
        "## Purpose\n\n"
        "This guide gives a practical operator workflow for diagnosing a broken technical service without guessing or making unsafe changes first. It is written for a support engineer or office power user who needs to collect evidence, isolate the failing layer, apply a low-risk fix, and escalate with useful notes when the issue is outside their control.\n\n"
        "## Prerequisites\n\n"
        "Before starting, confirm the affected user, device, service name, approximate start time, error message, and whether the issue affects one person, one location, or everyone. Keep access to the admin console, monitoring dashboard, logs, and a known working account if available. Prepare common tools such as a browser, terminal, ping, traceroute, nslookup or dig, curl, systemctl or services.msc, and a notes file for timestamps.\n\n"
        "## Configuration Steps\n\n"
        "1) Define the failure clearly: write one sentence such as \"Users on office WiFi cannot reach the payroll web app after login\" instead of \"the system is down\".\n"
        "2) Check scope: test one affected device, one unaffected device, and if possible a different network. This separates account, device, network, and service problems.\n"
        "3) Check local basics: confirm power, cable or WiFi connection, IP address, disk space, time/date sync, and whether a restart is pending.\n"
        "4) Check network reachability: run ping to the gateway, ping 8.8.8.8, then nslookup example.com or dig example.com. If IP ping works but name lookup fails, treat it as DNS first.\n"
        "5) Check service response: use curl -I or the browser developer network tab to capture HTTP status, redirects, certificate errors, and timeout timing.\n"
        "6) Check recent changes: review deployments, password changes, firewall edits, certificate renewals, license limits, scheduled maintenance, and provider incidents from the last 24 hours.\n"
        "7) Apply only reversible first fixes: restart the affected app, clear a local cache, renew DHCP, reconnect VPN, or restart the service if you own it and have a rollback path.\n"
        "8) Record every action with time, expected result, actual result, and whether the symptom changed.\n\n"
        "## Verification\n\n"
        "Verify recovery from the user's perspective, not only from the admin console. Confirm the affected workflow works end to end, the same error no longer appears, and a second device or account also succeeds where practical. For network or service issues, include at least one reachability check, one DNS check, one application response check, and one user-level workflow check. If monitoring exists, confirm alerts have cleared and error rates are trending back to normal.\n\n"
        "## Troubleshooting\n\n"
        "1) If only one user is affected, check account lockout, permissions, saved credentials, browser profile, local cache, and device-specific network settings.\n"
        "2) If one location is affected, check switch, access point, DHCP, DNS, firewall, ISP status, and recent local network changes.\n"
        "3) If everyone is affected, check service health, deployment logs, database status, certificate expiry, identity provider status, and external provider incidents.\n"
        "4) If ping works but browser access fails, check DNS, proxy, certificate trust, firewall rules, HTTP status, and application logs.\n"
        "5) If the issue returns after a restart, treat the restart as symptom relief only and continue root-cause investigation using logs and change history.\n\n"
        "## Safety Notes\n\n"
        "Do not delete logs, reset passwords, change firewall rules, update firmware, restart shared infrastructure, or run destructive commands unless you own the system and have approval or a documented rollback. Do not paste secrets, tokens, private keys, customer records, or full production configuration into chat or tickets. If data loss, security exposure, payment, booking, upload, login submission, or final submit actions are involved, stop and ask for explicit confirmation before acting.\n\n"
        "## Next Steps\n\n"
        "If the issue is resolved, document the root cause, fix, verification evidence, and prevention item. If it is unresolved, escalate with timestamps, affected users, screenshots or error text, command outputs, recent changes, and the exact steps already attempted. Create a follow-up task for monitoring, permanent remediation, and any user communication needed after service recovery.\n"
    )


def _router_network_topic(topic: str) -> bool:
    lowered = re.sub(r"\s+", " ", str(topic).lower()).strip()
    return any(marker in lowered for marker in ("router", "wifi", "wi fi", "wireless network", "network setup", "network troubleshooting"))


def _router_network_repair_markdown() -> str:
    return (
        "# Router And WiFi Setup Guide\n\n"
        "## Purpose\n\n"
        "This guide sets up a home or small-office router safely: admin access, WAN/internet settings, WiFi name and password, WPA2/WPA3 security, firmware handling, verification, and troubleshooting. It uses generic wording because exact menu names vary by router brand.\n\n"
        "## Prerequisites\n\n"
        "1) Router powered on, modem connected to the router WAN port, and a laptop or phone connected by Ethernet or the default WiFi network.\n"
        "2) Router admin address from the label or manual, commonly 192.168.0.1, 192.168.1.1, or a vendor app.\n"
        "3) ISP details if required: PPPoE username/password, VLAN ID, static IP settings, or whether DHCP is enough.\n"
        "4) New admin password, WiFi SSID, WiFi password, and a safe place to store them privately.\n\n"
        "## Configuration Steps\n\n"
        "1) Open the admin interface in a browser or vendor app, then log in with the admin credentials from the router label or the credentials you already changed.\n"
        "2) Change the default administrative password immediately. Use a unique password, confirm it, save it, and log back in to verify the new password works before changing anything else.\n"
        "3) Configure WAN or internet settings. Choose DHCP if the ISP modem provides an address automatically, or enter PPPoE/static/VLAN details only if your ISP gave them to you. Save and wait for the router to show a WAN IP.\n"
        "4) Configure the WiFi network name. Set a clear SSID that does not expose private information such as your full address or phone number.\n"
        "5) Configure the WiFi password. Use a strong password of at least 12 characters and do not reuse your router admin password.\n"
        "6) Set WiFi security to WPA2-Personal, WPA3-Personal, or WPA2/WPA3 mixed mode depending on device compatibility. Avoid open WiFi and avoid WEP.\n"
        "7) Check firmware update status from the router admin page. If an update is available, read the release note, keep power connected, avoid interrupting the router, and update only when you have time to recover if it reboots.\n"
        "8) Save or apply the configuration. Reconnect your phone or laptop to the new SSID using the new WiFi password.\n\n"
        "## Verification\n\n"
        "1) Confirm the router admin page shows internet connected and has a WAN IP address.\n"
        "2) From a connected client, run ping 8.8.8.8 to verify external reachability.\n"
        "3) Run nslookup example.com or open a known website to verify DNS resolution.\n"
        "4) Join the new WiFi SSID from at least one phone and one laptop if available.\n"
        "5) Confirm speed and stability with a short browsing test, a video playback test, and a call or messaging app test.\n\n"
        "## Troubleshooting\n\n"
        "1) If admin login fails, check the router label, confirm you are on the router network, try the vendor app, or use the reset process only if you accept losing current settings.\n"
        "2) If there is no WAN IP, check the cable from modem to WAN port, reboot the modem once, confirm ISP details, and check whether PPPoE or VLAN settings are required.\n"
        "3) If WiFi does not appear, confirm wireless radios are enabled, SSID broadcast is on, and the router is not in access-point-only or bridge mode unexpectedly.\n"
        "4) If the WiFi password fails, retype it carefully, remove the saved network on the phone/laptop, and reconnect.\n"
        "5) If internet works by Ethernet but not WiFi, review WiFi security mode, DHCP, band steering, and whether the client supports WPA3.\n\n"
        "## Safety Notes\n\n"
        "Do not share the router admin password, WiFi password, ISP credentials, or exported configuration file. Do not update firmware during unstable power or while someone depends on the connection for urgent work. Keep a backup or screenshot of the old settings before major changes. Stop before payment, ISP account changes, upload, login submission, or final submit actions unless the exact action is explicitly approved.\n\n"
        "## Next Steps\n\n"
        "Rename known connected devices in the router dashboard, create a guest WiFi network if needed, disable WPS if you do not use it, schedule firmware review monthly, and keep a private note with the router admin URL, SSID, and recovery steps without exposing passwords.\n"
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
    audience = re.match(
        r"^(?:actually,?\s+)?(?:(?:it[’']?s|it\s+is)\s+for|make\s+it\s+for|for)\s+(.+)$",
        cleaned,
        re.I,
    )
    if audience and audience.group(1).strip():
        return f"make it for {audience.group(1).strip(' .')}", save_copy
    patterns: tuple[tuple[str, bool], ...] = (
        (
            r"^(?:update|edit|revise|change|modify)\s+"
            r"(that\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|this\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|the\s+(?:last|latest)\s+(?:document|doc|file)|the\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|that|it|this)\s*"
            r"(?:to|into|with|so\s+that)?\s*(.+)$",
            True,
        ),
        (
            r"^(?:make|turn)\s+"
            r"(that\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|this\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|the\s+(?:last|latest)\s+(?:document|doc|file)|the\s+(?:document|doc|file|deck|presentation|powerpoint|spreadsheet|excel|workbook)|that|it|this)\s+"
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
    contextual = re.match(
        r"^(?:in|for)\s+(?:an?\s+|the\s+)?"
        r"(.+?\b(?:worksheet|sheet|workbook|spreadsheet|excel|document|doc|file|deck|presentation|powerpoint|tracker)\b)"
        r"\s*,?\s+(.+)$",
        cleaned,
        re.I,
    )
    if contextual and contextual.group(2).strip():
        target = contextual.group(1).strip(" .")
        detail = contextual.group(2).strip(" .")
        if _looks_like_document_edit_instruction(f"{detail} {target}"):
            return f"{detail} in {target}", save_copy
    direct = re.match(r"^(?:update|edit|revise|change|modify|set|add|append|include|insert)\s+(.+)$", cleaned, re.I)
    if direct and direct.group(1).strip():
        instruction = direct.group(1).strip(" .")
        if _looks_like_document_edit_instruction(instruction):
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
        re.search(r"\b(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*[- ]?\s*(?:day|days|slides?|pages?|rows?|columns?)\b", lowered)
        or re.search(
            r"\b(?:add|append|remove|delete|include|insert|replace|rewrite|rename|reformat|format|"
            r"heading|title|summary|section|chapter|slide|speaker notes?|presenter notes?|image|photo|chart|links?|"
            r"table|sheet|worksheet|formula|budget|itinerary|recommendations?|config|putty|ssh|cli|"
            r"audience|executive|ed|director|board|boss|stakeholders?|"
            r"location|destination|city|country|place|venue|route|trip length|duration|"
            r"travellers?|travelers?|people|persons?|people count|number of people|pax|adult|adults|guests?|"
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
    title = re.sub(
        r"^(?:Excel\s+)?(?:Budget\s+Tracker|Spreadsheet|Workbook)\s+For\s+",
        "",
        title,
        flags=re.I,
    )
    title = re.sub(r"^Create\s+A\s+For\s+(?:A\s+)?", "", title, flags=re.I)
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


def _draft_override_requested(instruction: str) -> bool:
    lowered = " ".join(str(instruction).lower().split())
    return any(
        marker in lowered
        for marker in (
            "give me the draft",
            "give me draft",
            "just give me",
            "even if qa fails",
            "even though qa failed",
            "even if it fails",
            "i will review",
            "i'll review",
            "i have permission",
            "i have all the permission",
            "open the draft",
            "send the draft",
        )
    )


def _word_quality_hard_blocks(quality: ArtifactQualityResult) -> bool:
    for issue in getattr(quality, "issue_details", []) or []:
        rule_id = str(getattr(issue, "rule_id", "") or "")
        message = str(getattr(issue, "message", "") or "").lower()
        if rule_id in {"docx.open", "docx.visual_layout"}:
            return True
        if "could not be opened" in message or "corrupt" in message:
            return True
    return False


async def _preserve_failed_word_draft(db_path: str, target: Path) -> Path | None:
    if not target.exists():
        return None
    draft_path = versioned_path(target.parent / f"{target.stem}-draft-v1{target.suffix}")
    await asyncio.to_thread(shutil.copy2, target, draft_path)
    await upsert_preference(db_path, LAST_DRAFT_DOC_KEY, str(draft_path), source="document")
    return draft_path


def _router_putty_topic(topic: str) -> bool:
    lowered = str(topic).lower()
    return "router" in lowered and any(marker in lowered for marker in ("putty", "ssh", "serial", "console", "cli", "command"))
