from __future__ import annotations

import json

import aiosqlite

from security_manifest import SecurityManifest, get_manifest, manifest_summary, upsert_manifest


async def init_mcp_registry(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS mcp_servers (
                name TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                env_needs TEXT DEFAULT '[]',
                status TEXT DEFAULT 'proposed',
                permission_scope TEXT DEFAULT '',
                owner TEXT DEFAULT 'Zainal',
                last_used DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS mcp_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def propose_mcp_server(
    db_path: str,
    name: str,
    command: str,
    env_needs: list[str] | None = None,
    permission_scope: str = "",
) -> None:
    await init_mcp_registry(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO mcp_servers (name, command, env_needs, permission_scope)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                command = excluded.command,
                env_needs = excluded.env_needs,
                permission_scope = excluded.permission_scope,
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, command, json.dumps(env_needs or []), permission_scope),
        )
        await db.commit()
    await upsert_manifest(db_path, _manifest_for_mcp(name, permission_scope))
    await record_mcp_usage(db_path, name, "proposed", permission_scope)


async def set_mcp_status(db_path: str, name: str, status: str) -> bool:
    if status not in {"proposed", "approved", "enabled", "disabled"}:
        return False
    await init_mcp_registry(db_path)
    current = await _get_mcp_server(db_path, name)
    if not current:
        return False
    if status == "enabled" and current["status"] != "approved":
        return False
    if status == "enabled" and not await get_manifest(db_path, "mcp", current["name"]):
        return False
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            UPDATE mcp_servers
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE lower(name) = lower(?)
            """,
            (status, name),
        )
        await db.commit()
    if cursor.rowcount:
        await record_mcp_usage(db_path, name, status, "")
    return cursor.rowcount > 0


async def _get_mcp_server(db_path: str, name: str) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM mcp_servers WHERE lower(name) = lower(?)", (name,))
        row = await cursor.fetchone()
    return dict(row) if row else None


async def list_mcp_servers(db_path: str, status: str | None = None) -> list[dict]:
    await init_mcp_registry(db_path)
    query = "SELECT * FROM mcp_servers"
    params: tuple[str, ...] = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query + " ORDER BY updated_at DESC", params)
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def audit_mcp_server(db_path: str, name: str) -> str:
    rows = await list_mcp_servers(db_path)
    row = next((item for item in rows if item["name"].lower() == name.lower()), None)
    if not row:
        return "I could not find that MCP tool."
    manifest = await get_manifest(db_path, "mcp", row["name"])
    events = await recent_mcp_usage(db_path, row["name"])
    lines = [
        f"MCP: {row['name']} ({row['status']})",
        f"Command: {row['command']}",
        f"Scope: {row['permission_scope'] or 'not declared'}",
    ]
    if manifest:
        lines.append(manifest_summary(manifest))
    if events:
        lines.append("Recent use: " + ", ".join(f"{e['action']}" for e in events[:5]))
    return "\n".join(lines)


async def record_mcp_usage(db_path: str, name: str, action: str, detail: str = "") -> None:
    await init_mcp_registry(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO mcp_usage_events (name, action, detail) VALUES (?, ?, ?)",
            (name, action, detail[:500]),
        )
        await db.execute("UPDATE mcp_servers SET last_used = CURRENT_TIMESTAMP WHERE name = ?", (name,))
        await db.commit()


async def recent_mcp_usage(db_path: str, name: str | None = None, limit: int = 10) -> list[dict]:
    await init_mcp_registry(db_path)
    query = "SELECT name, action, detail, created_at FROM mcp_usage_events"
    params: tuple[str | int, ...] = (limit,)
    if name:
        query += " WHERE lower(name) = lower(?)"
        params = (name, limit)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query + " ORDER BY id DESC LIMIT ?", params)
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def _manifest_for_mcp(name: str, scope: str) -> SecurityManifest:
    text = scope.lower()
    perms = {
        "read_files": "file" in text or "read" in text,
        "write_files": "write" in text,
        "browse_web": "web" in text or "browser" in text,
        "external_api": "api" in text or "account" in text,
        "create_artifacts": "artifact" in text or "file" in text,
    }
    return SecurityManifest("mcp", name, perms, hard_blocks=["private_exposure", "secrets"])
