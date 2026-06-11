from __future__ import annotations

import pptx_helpers.visual_assets as _impl
from pptx_helpers.visual_assets import (
    EMU_PER_INCH,
    IMAGE_SLOT_NAME,
    PLAIN_TOPIC_MARKERS,
    SLOT_INSET_INCHES,
    VISUAL_TOPIC_MARKERS,
    _add_picture_cover,
    _apply_center_crop,
    _fallback_visual,
    _fit_visual_to_slot,
    _image_prompt,
    _image_prompts,
    _image_scratch_dir,
    _image_timeout_seconds,
    _inset_slot,
    _insert_visuals,
    _named_image_slot,
    _picture_slot,
    _slot_for_slide,
    _slot_prompt,
    _target_slide_index,
    generate_gemini_image,
    required_visual_image_count,
    topic_benefits_from_visuals,
    visual_image_cap,
    visual_image_target,
)


async def add_gemini_visual_asset(*args, **kwargs):
    _impl.generate_gemini_image = generate_gemini_image
    return await _impl.add_gemini_visual_asset(*args, **kwargs)

__all__ = [
    "_add_picture_cover",
    "_apply_center_crop",
    "_fallback_visual",
    "_fit_visual_to_slot",
    "_image_prompt",
    "_image_prompts",
    "_image_scratch_dir",
    "_image_timeout_seconds",
    "_inset_slot",
    "_insert_visuals",
    "_named_image_slot",
    "_picture_slot",
    "_slot_for_slide",
    "_slot_prompt",
    "_target_slide_index",
    "add_gemini_visual_asset",
    "EMU_PER_INCH",
    "generate_gemini_image",
    "IMAGE_SLOT_NAME",
    "PLAIN_TOPIC_MARKERS",
    "required_visual_image_count",
    "SLOT_INSET_INCHES",
    "topic_benefits_from_visuals",
    "VISUAL_TOPIC_MARKERS",
    "visual_image_cap",
    "visual_image_target",
]
