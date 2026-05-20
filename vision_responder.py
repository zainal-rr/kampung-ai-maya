from __future__ import annotations

import os
import re

from activation import current_work_location
from assistant_command_helpers import direct_key
from cost_tracker import record_usage
from language_policy import language_instruction
from maya_eye_overlay import clear_preview_target, set_preview_targets
from maya_eye_preview import start_preview
from models import TheSenses
from storage import get_preference, list_preferences, upsert_preference
from vision_markup import draw_visual_marks, image_marker, parse_targets, remove_target_line
from vision_service import CiscoVisionService, VisionSnapshot
from vision_session import guided_sight_active


VISION_QUERIES = {
    "can you see",
    "can you see me",
    "what can you see",
    "what do you see",
    "what are you seeing",
    "describe what you see",
    "look around",
    "use your eyes",
}


class VisionResponder:
    def __init__(self, db_path: str, capture_service=None, senses=None):
        self.db_path = db_path
        self.capture_service = capture_service or CiscoVisionService()
        self.senses = senses or TheSenses(
            os.getenv("GOOGLE_API_KEY", "dummy"),
            os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
        )
        self.pro_senses = senses or TheSenses(
            os.getenv("GOOGLE_API_KEY", "dummy"),
            os.getenv("GEMINI_PRO_MODEL", "gemini-3.1-pro"),
        )

    async def handle(self, text: str, channel: str) -> str | None:
        active = await guided_sight_active(self.db_path)
        if not self._is_query(text, active):
            return None
        if os.getenv("ENABLE_VISION_CAMERA", "0") != "1":
            return "I can't see right now. Live vision is switched off."
        if not await self._allowed_for_channel(channel, active):
            return "Use /see first so I have permission to look."
        if channel == "imac" or active:
            start_preview()

        snapshot = self.capture_service.capture_once()
        await self._record_snapshot(snapshot)
        if not snapshot.visible or not snapshot.image_bytes:
            return f"I can't see right now. {snapshot.status}"
        return await self._describe(text, snapshot, await self._orientation_context(), channel)

    @staticmethod
    def _is_query(text: str, active: bool) -> bool:
        key = direct_key(text)
        if key in VISION_QUERIES or key.startswith(("maya eye ", "camera ")):
            return True
        return active and any(marker in key for marker in GUIDED_MARKERS)

    async def _allowed_for_channel(self, channel: str, active: bool) -> bool:
        if channel == "imac":
            return True
        return active and await current_work_location(self.db_path) == "imac"

    async def _describe(self, request: str, snapshot: VisionSnapshot, orientation_context: str, channel: str) -> str:
        prompt = (
            "You are Maya giving guided visual help through the approved Cisco camera. "
            f"User request: {request}. "
            "Do not merely describe the table. Help the user complete the visible task. "
            "Give the next practical step in a concise friendly way. "
            f"{language_instruction(request)} "
            "Only use visual targets when pointing is useful. Descriptive questions like shape, color, "
            "or general identity usually need TARGET: none. "
            "If pointing helps, end with TARGET: label, x, y, radius. For several useful points, "
            "write several TARGET lines, one per target. Use 0 to 1000 image coordinates. "
            "Small targets render as circles, larger targets or close clusters render as rectangles. "
            "For rows, labels, stickers, or grouped ports, prefer one clean area over many cluttered points. "
            "If several circles would crowd the preview, mark the whole useful group instead. "
            "If no clear target exists, end with TARGET: none. "
            "Only return targets that are visible enough to point at confidently. "
            "End with CONFIDENCE: 0-100 based on how sure you are. "
            "If the user asks to read a label, model, text, or sticker and it is not readable, use TARGET: none. "
            "If the user asks for a model or label and does not ask you to show where, prefer TARGET: none. "
            "If the user asks where the model or label is, target the exact readable model text or full sticker, "
            "never a barcode, serial number, or nearby unrelated area. "
            "Describe locations from Zainal's side of the desk, not from the camera side. "
            "If the camera view is reversed, translate left, right, front, and back for Zainal. "
            "For labels or model numbers, mentally rotate or orient the visible text for Zainal before reading it. "
            f"{orientation_context}"
            "Do not mention model providers. Do not guess private identity. "
            "If the image is unclear, say what is uncertain."
        )
        description = (await self.senses.describe_image(snapshot.image_bytes, prompt)).strip()
        await record_usage(self.db_path, "gemini_flash_vision_calls", 1, "camera snapshot")
        if not description:
            return "I can see, but I could not work out the next step clearly."
        description = await self._maybe_escalate_to_pro(request, snapshot.image_bytes, prompt, description)
        clean = remove_target_line(description)
        clean = self._remove_confidence_line(clean)
        targets = self._safe_targets(request, clean, parse_targets(description))
        marker = ""
        if targets:
            set_preview_targets(targets)
            if channel == "telegram":
                image_path = draw_visual_marks(snapshot.image_bytes, targets)
                marker = f"\n{image_marker(image_path)}" if image_path else ""
        else:
            clear_preview_target()
        return f"I see. {clean}{marker}"

    async def _maybe_escalate_to_pro(
        self,
        request: str,
        image_bytes: bytes,
        prompt: str,
        flash_answer: str,
    ) -> str:
        if not self._pro_may_help(request, flash_answer, self._confidence(flash_answer)):
            return flash_answer
        pro_prompt = (
            f"{prompt} "
            "Flash may be uncertain here. Only improve the answer if the image contains enough detail. "
            "If higher reasoning will not help because the frame is blurry or blocked, say what to change instead."
        )
        pro_answer = (await self.pro_senses.describe_image(image_bytes, pro_prompt)).strip()
        await record_usage(self.db_path, "gemini_pro_vision_calls", 1, "camera escalation")
        return pro_answer or flash_answer

    async def _record_snapshot(self, snapshot: VisionSnapshot) -> None:
        visible = "visible" if snapshot.visible else "not visible"
        await upsert_preference(self.db_path, "maya_eye_last_status", f"{visible}: {snapshot.status}", source="vision")

    @classmethod
    def _safe_targets(
        cls,
        request: str,
        answer: str,
        targets: list[tuple[str, int, int, int]],
    ) -> list[tuple[str, int, int, int]]:
        if not targets or not cls._wants_pointing(request):
            return []
        lowered_request = request.lower()
        lowered_answer = answer.lower()
        asks_to_read = any(
            marker in lowered_request
            for marker in ("model", "label", "serial", "sticker", "text", "read", "what does")
        )
        uncertain = any(
            marker in lowered_answer
            for marker in (
                "can't read", "cannot read", "cant read", "not readable", "unreadable",
                "not clear", "unclear", "blurry", "too small", "can't see", "cannot see",
                "not visible", "move it closer", "bring it closer",
            )
        )
        if asks_to_read and uncertain:
            return []
        if asks_to_read:
            return [target for target in targets if not cls._barcode_or_serial_target(target)]
        return targets

    @staticmethod
    def _wants_pointing(request: str) -> bool:
        lowered = request.lower()
        markers = (
            "where", "which port", "what port", "port should", "port can",
            "circle", "highlight", "show me", "point", "which one", "plug",
            "press", "button", "cable", "use port", "open button",
        )
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _confidence(answer: str) -> int | None:
        match = re.search(r"CONFIDENCE:\s*(\d{1,3})", answer, re.IGNORECASE)
        if not match:
            return None
        return max(0, min(100, int(match.group(1))))

    @staticmethod
    def _remove_confidence_line(text: str) -> str:
        return re.sub(r"\s*CONFIDENCE:\s*\d{1,3}", "", text, flags=re.IGNORECASE).strip()

    @staticmethod
    def _pro_may_help(request: str, answer: str, confidence: int | None) -> bool:
        lowered_request = request.lower()
        lowered_answer = answer.lower()
        if "look carefully" in lowered_request or "double check" in lowered_request:
            return True
        risky = any(marker in lowered_request for marker in ("power", "voltage", "security", "factory reset"))
        tiny_text = any(marker in lowered_request for marker in ("label", "model", "serial", "sticker", "text", "read"))
        blurry = any(marker in lowered_answer for marker in ("blurry", "unclear", "not readable", "too small"))
        low_confidence = confidence is not None and confidence < 60
        return risky or tiny_text or blurry or low_confidence

    @staticmethod
    def _barcode_or_serial_target(target: tuple[str, int, int, int]) -> bool:
        label = target[0].lower()
        return any(marker in label for marker in ("barcode", "serial", "qr", "mac", "imei"))

    async def _orientation_context(self) -> str:
        calibrated = await get_preference(self.db_path, "maya_eye_orientation")
        if calibrated:
            return (
                f"Important orientation rule: {calibrated}. "
                "Use this calibration when describing positions from Zainal's side. "
            )
        preferences = await list_preferences(self.db_path, limit=20)
        for item in preferences:
            value = item["value"]
            lowered = value.lower()
            if "reverse" in lowered and ("front" in lowered or "left" in lowered or "right" in lowered):
                return (
                    "Important orientation rule: the camera view may be reversed in depth, "
                    "but do not swap left and right unless a calibrated note says to. "
                    f"Saved note: {value}. "
                )
        return ""


GUIDED_MARKERS = (
    "which port",
    "what port",
    "where is",
    "where do i",
    "how do i",
    "how to",
    "open this",
    "press",
    "plug",
    "button",
    "port",
    "cable",
    "router",
    "camera",
    "device",
    "circle",
    "show me",
    "is this",
    "this one",
    "this cable",
)
