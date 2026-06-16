from __future__ import annotations

"""Compatibility facade for active iMac context inspection.

The implementation lives in `maya_voice.active_context_inspector` so the root
module stays a stable public import without becoming another large working
surface.
"""

from maya_voice.active_context_inspector import (
    ActiveContextInspector,
    active_context_instruction,
    inspect_active_context,
)


__all__ = [
    "ActiveContextInspector",
    "active_context_instruction",
    "inspect_active_context",
]
