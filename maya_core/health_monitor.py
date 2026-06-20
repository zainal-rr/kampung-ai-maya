from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


class HealthReporter:
    def __init__(self, db_path: str, log_dir: str = "logs"):
        self.db_path = db_path
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.health_path = self.log_dir / "health.json"
        self.interval = int(os.getenv("HEALTH_HEARTBEAT_SECONDS", "30"))

    async def run(self) -> None:
        while True:
            await self.write_snapshot()
            await asyncio.sleep(self.interval)

    async def write_snapshot(self) -> None:
        snapshot = {
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "pid": os.getpid(),
            "imac_channel": os.getenv("ENABLE_IMAC_CHANNEL", "0"),
            "agent_runtime": os.getenv("ENABLE_AGENT_RUNTIME", "1"),
            "routines": os.getenv("ENABLE_ROUTINES", "1"),
            "omi_adapter": os.getenv("ENABLE_OMI_ADAPTER", "0"),
            "mudra_adapter": os.getenv("ENABLE_MUDRA_ADAPTER", "0"),
            "external_camera_adapter": os.getenv("ENABLE_EXTERNAL_CAMERA_ADAPTER", "0"),
            "telegram": "1" if os.getenv("TELEGRAM_BOT_TOKEN") else "0",
            "task_counts": await self._task_counts(),
            "routine_count": await self._routine_count(),
        }
        self.health_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    async def _task_counts(self) -> dict[str, int]:
        query = (
            "SELECT "
            "SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN status='running' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN status='awaiting_confirmation' THEN 1 ELSE 0 END) "
            "FROM tasks"
        )
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query)
            row = await cursor.fetchone()
        return {
            "pending": int(row[0] or 0),
            "running": int(row[1] or 0),
            "awaiting_confirmation": int(row[2] or 0),
        }

    async def _routine_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM routines WHERE active = 1")
            row = await cursor.fetchone()
        return int(row[0] or 0)
