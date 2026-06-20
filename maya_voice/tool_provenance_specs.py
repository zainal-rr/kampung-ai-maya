from __future__ import annotations

from maya_core.provenance import SOURCE_KINDS


def provenance_schema(description: str = "Structured source/trust metadata.") -> dict:
    return {
        "type": "object",
        "description": description,
        "properties": {
            "source_kind": {
                "type": "string",
                "enum": sorted(SOURCE_KINDS),
            },
            "source_id": {"type": "string"},
            "untrusted_influence": {"type": "boolean"},
            "injection_detected": {"type": "boolean"},
            "risk_notes": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": True,
    }
