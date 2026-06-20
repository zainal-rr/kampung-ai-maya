from __future__ import annotations

import json
from dataclasses import dataclass, field

import aiosqlite


PERMISSIONS = (
    "read_files", "write_files", "delete_files", "send_files", "browse_web",
    "browser_click", "form_fill", "use_accounts", "external_api",
    "write_memory", "create_artifacts",
)
RISKY = {"delete_files", "send_files", "browser_click", "form_fill", "use_accounts", "external_api"}


@dataclass
class SecurityManifest:
    subject_type: str
    subject_id: str
    permissions: dict[str, bool] = field(default_factory=dict)
    approval_required: list[str] = field(default_factory=list)
    hard_blocks: list[str] = field(default_factory=list)
    notes: str = ""

    def normalized(self) -> dict:
        perms = {key: bool(self.permissions.get(key, False)) for key in PERMISSIONS}
        approvals = sorted(set(self.approval_required) | (RISKY & {k for k, v in perms.items() if v}))
        blocks = sorted(set(self.hard_blocks))
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "permissions": perms,
            "approval_required": approvals,
            "hard_blocks": blocks,
            "notes": self.notes[:500],
        }


async def init_manifest_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS security_manifests (
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(subject_type, subject_id)
            )
            """
        )
        await db.commit()


async def upsert_manifest(db_path: str, manifest: SecurityManifest) -> None:
    await init_manifest_db(db_path)
    payload = json.dumps(validate_manifest(manifest), sort_keys=True)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO security_manifests (subject_type, subject_id, manifest_json)
            VALUES (?, ?, ?)
            ON CONFLICT(subject_type, subject_id) DO UPDATE SET
                manifest_json = excluded.manifest_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (manifest.subject_type, manifest.subject_id, payload),
        )
        await db.commit()


async def get_manifest(db_path: str, subject_type: str, subject_id: str) -> dict | None:
    await init_manifest_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT manifest_json FROM security_manifests WHERE subject_type = ? AND subject_id = ?",
            (subject_type, subject_id),
        )
        row = await cursor.fetchone()
    return json.loads(row[0]) if row else None


async def list_manifests(db_path: str, subject_type: str | None = None) -> list[dict]:
    await init_manifest_db(db_path)
    query = "SELECT manifest_json FROM security_manifests"
    params: tuple[str, ...] = ()
    if subject_type:
        query += " WHERE subject_type = ?"
        params = (subject_type,)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(query + " ORDER BY updated_at DESC", params)
        rows = await cursor.fetchall()
    return [json.loads(row[0]) for row in rows]


def validate_manifest(manifest: SecurityManifest | dict) -> dict:
    data = manifest.normalized() if isinstance(manifest, SecurityManifest) else dict(manifest)
    if not data.get("subject_type") or not data.get("subject_id"):
        raise ValueError("Manifest needs subject_type and subject_id.")
    perms = data.get("permissions") or {}
    unknown = set(perms) - set(PERMISSIONS)
    if unknown:
        raise ValueError(f"Unknown permissions: {', '.join(sorted(unknown))}")
    data["permissions"] = {key: bool(perms.get(key, False)) for key in PERMISSIONS}
    data["approval_required"] = sorted(set(data.get("approval_required") or []))
    data["hard_blocks"] = sorted(set(data.get("hard_blocks") or []))
    return data


def manifest_summary(data: dict) -> str:
    allowed = [key for key, value in data.get("permissions", {}).items() if value]
    approvals = data.get("approval_required", [])
    blocks = data.get("hard_blocks", [])
    return (
        f"{data['subject_type']} {data['subject_id']}\n"
        f"Allowed: {', '.join(allowed) if allowed else 'none'}\n"
        f"Approval: {', '.join(approvals) if approvals else 'none'}\n"
        f"Blocked: {', '.join(blocks) if blocks else 'none'}"
    )
