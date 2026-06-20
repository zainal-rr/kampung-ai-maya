"""One-time UI schema helper.

The read-only UI server never mutates the Maya database. Run this helper
explicitly when the runtime is stopped or in a maintenance window to add the
event-envelope version columns used by SSE_PROTOCOL.md.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "session_history.db"


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def ensure_schema_version(db_path: Path = DB_PATH) -> list[str]:
    changed: list[str] = []
    with sqlite3.connect(db_path) as conn:
        for table in ("harness_events", "route_events"):
            if not _has_column(conn, table, "schema_version"):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN schema_version INTEGER DEFAULT 1")
                changed.append(table)
        conn.commit()
    return changed


def main() -> None:
    changed = ensure_schema_version()
    if changed:
        print("Added schema_version to: " + ", ".join(changed))
    else:
        print("schema_version already present")


if __name__ == "__main__":
    main()
