from __future__ import annotations

import os
import tempfile
from pathlib import Path

from maya_engine_lock import acquire_engine_lock


def main() -> None:
    old_env = os.environ.get("MAYA_ENGINE_LOCK")
    try:
        with tempfile.TemporaryDirectory(prefix="maya-engine-lock-") as tmp:
            first = acquire_engine_lock(lock_dir=tmp)
            _require(first is not None, "first engine lock acquire should succeed")
            second = acquire_engine_lock(lock_dir=tmp)
            _require(second is None, "second engine lock acquire must refuse duplicate engine")
            assert first is not None
            first.release()
            third = acquire_engine_lock(lock_dir=tmp)
            _require(third is not None, "engine lock must be reacquirable after release")
            assert third is not None
            third.release()

        with tempfile.TemporaryDirectory(prefix="maya-engine-lock-disabled-") as tmp:
            os.environ["MAYA_ENGINE_LOCK"] = "0"
            first = acquire_engine_lock(lock_dir=Path(tmp))
            second = acquire_engine_lock(lock_dir=Path(tmp))
            _require(first is not None and second is not None, "disabled lock should not block tests")
    finally:
        if old_env is None:
            os.environ.pop("MAYA_ENGINE_LOCK", None)
        else:
            os.environ["MAYA_ENGINE_LOCK"] = old_env
    print("maya_engine_lock_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
