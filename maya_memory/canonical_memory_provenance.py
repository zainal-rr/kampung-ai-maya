from __future__ import annotations

import aiosqlite

from maya_core.provenance import ensure_provenance, provenance_from_source_channel, provenance_to_json


async def ensure_canonical_memory_provenance_schema(db: aiosqlite.Connection) -> None:
    for ddl in (
        "ALTER TABLE canonical_memory_items ADD COLUMN provenance_json TEXT DEFAULT '{}'",
        "ALTER TABLE canonical_memory_items ADD COLUMN untrusted_influence INTEGER DEFAULT 0",
        "ALTER TABLE canonical_memory_items ADD COLUMN injection_detected INTEGER DEFAULT 0",
    ):
        try:
            await db.execute(ddl)
        except aiosqlite.OperationalError:
            pass


def resolve_memory_provenance(provenance: object, source_channel: str, source_ref: str) -> tuple[str, int, int]:
    if provenance is not None:
        prov = ensure_provenance(provenance, default_kind="unknown")
    else:
        prov = provenance_from_source_channel(source_channel, source_ref=source_ref)
    return provenance_to_json(prov), int(prov.untrusted_influence), int(prov.injection_detected)
