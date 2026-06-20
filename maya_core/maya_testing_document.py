from __future__ import annotations


def is_maya_testing_topic(topic: str) -> bool:
    low = topic.lower()
    if "autodesk" in low or "3d software" in low:
        return False
    maya_terms = ("maya", "kampung ai", "assistant")
    test_terms = ("test", "testing", "checklist", "pre-travel", "travel", "before leaving")
    return any(term in low for term in maya_terms) and any(term in low for term in test_terms)


def pre_travel_sections() -> list[tuple[str, list[str]]]:
    return [
        ("Purpose", [
            "Lock Maya's useful daily behavior before Zainal is away from the iMac from 25 May to 8 June 2026.",
            "Treat this as a practical Kampung AI assistant test plan, not a 3D software checklist.",
        ]),
        ("Office Draft Quality", [
            "Create and inspect one PowerPoint, one Word document, and one Excel workbook from Telegram.",
            "Pass means files open cleanly, are attached in Telegram, and contain relevant Kampung AI content.",
            "PowerPoint may be draft-level, but it must not have truncation, repair alerts, or wrong-topic content.",
        ]),
        ("Conversation And Routing", [
            "Test normal Telegram chat, Malay or Manglish mirroring, memory recall, and concise replies.",
            "Use /route after representative prompts to confirm Gemini, Claude, Artisan Codex, Grok, and /complex routing.",
            "Typed Telegram messages should stay text-only unless the input was voice or voice is requested.",
        ]),
        ("Voice Before Travel", [
            "Test Telegram voice notes and Ara replies before relying on voice while away.",
            "Only test local iMac speech-to-speech while physically near the iMac.",
            "If local voice feels unstable, leave ENABLE_XAI_VOICE_AGENT=0 during travel.",
        ]),
        ("Screen, Camera, And Remote Maintenance", [
            "Use /screen and /see only for deliberate baseline checks before travel.",
            "Confirm Cisco Desk Camera 4K is used for sight and that toggles turn screen or camera awareness off.",
            "Use Splashtop Streamer for remote maintenance and visual file checks, not as proof of local voice quality.",
        ]),
        ("Safety And Recovery", [
            "Delete, send, upload, booking, payment, deploy, and restart actions must ask for confirmation.",
            "Private exposure such as API keys, cards, passwords, OTP, and bank data must be hard blocked.",
            "Before leaving, run MAYA_TEST_MODE=1 ./venv/bin/python may1_rehearsal.py and keep Omi and Mudra disabled.",
        ]),
    ]
