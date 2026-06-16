from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from assistant_model_lanes import ModelLanes


def main() -> None:
    _require(
        not ModelLanes.should_use_artisan_path(
            "I am tired today and still need to keep testing Maya. What should I focus on next?"
        ),
        "daily-life testing prompt should not route to Artisan",
    )
    _require(
        not ModelLanes.should_use_artisan_path("what tests should I run for Telegram?"),
        "test-planning question should not route to Artisan",
    )
    _require(
        not ModelLanes.should_use_artisan_path("Compare OpenHands and Claude Code briefly."),
        "product comparison should not route to Artisan just because it says Claude Code",
    )
    _require(
        not ModelLanes.should_use_artisan_path("explain Claude Code architecture"),
        "explanation prompt should not route to Artisan",
    )
    _require(
        ModelLanes.should_use_artisan_path("debug this python function"),
        "coding debug request should route to Artisan",
    )
    _require(
        ModelLanes.should_use_artisan_path("build me a web app for habit tracking"),
        "app-building request should route to Artisan",
    )
    _require(
        ModelLanes.should_use_artisan_path("make a printable phone stand in Blender"),
        "maker request should route to Artisan",
    )
    print("artisan_routing_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
