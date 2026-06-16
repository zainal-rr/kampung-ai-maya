from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from artisan_runner import latest_artisan_delivery_text
from harness_store import init_harness_db, upsert_run
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artisan-delivery-") as tmp:
        root = Path(tmp)
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)

        app = root / "Maya" / "Projects" / "habit-app"
        app.mkdir(parents=True)
        (app / "index.html").write_text("<!doctype html><html><body>Habits</body></html>", "utf-8")
        (app / "README.md").write_text("# Habit App\n\nOpen index.html.\n", "utf-8")
        await upsert_run(
            db_path,
            {
                "run_id": "hrn_appsmoke",
                "thread_id": "maya:artisan",
                "channel": "telegram",
                "workflow_type": "artisan_app",
                "goal": "habit app",
                "current_step": 1,
                "working_directory": str(app),
                "summary": "Artisan app QA passed.",
                "app_qa": {"app_root": str(app), "preview_path": "", "passed": True},
            },
            status="completed",
        )
        app_reply = await latest_artisan_delivery_text(db_path, "app", "telegram")
        _require("Last app:" in app_reply and "[file:" in app_reply and "habit-app-app.zip" in app_reply, app_reply)

        maker = root / "Maya" / "Projects" / "hook" / "3d"
        maker.mkdir(parents=True)
        stl = maker / "hook.stl"
        blend = maker / "hook.blend"
        readme = maker / "README.md"
        preview = maker / "hook-preview.png"
        stl.write_bytes(b"0" * 300)
        blend.write_bytes(b"0" * 1200)
        readme.write_text("# Hook\n\nDo not print without confirmation.\n", "utf-8")
        preview.write_bytes(b"0" * 1500)
        await upsert_run(
            db_path,
            {
                "run_id": "hrn_makersmoke",
                "thread_id": "maya:artisan",
                "channel": "telegram",
                "workflow_type": "artisan_3d",
                "goal": "wall hook",
                "current_step": 1,
                "working_directory": str(maker),
                "summary": "Blender maker QA passed.",
                "maker_qa": {
                    "mesh_files": [str(stl)],
                    "blend_files": [str(blend)],
                    "readme_files": [str(readme)],
                    "preview_files": [str(preview)],
                    "dimensions_mm": {"hook.stl": [35, 28, 55]},
                    "passed": True,
                },
            },
            status="completed",
        )
        maker_reply = await latest_artisan_delivery_text(db_path, "maker", "telegram")
        _require("Last 3D model:" in maker_reply and "not sliced" in maker_reply and str(stl) in maker_reply, maker_reply)
    print("artisan_delivery_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
