# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

import asyncio

import numpy as np

import maya_core.local_wake_scorer as local_wake_scorer
from maya_core.local_wake_scorer import LocalWakeScorerTranscriptSource


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    calls = {"record": 0}

    def fake_record(device, seconds):
        calls["record"] += 1
        return np.zeros(16000 * seconds, dtype=np.int16)

    def fake_index(name):
        return 1

    original_record = local_wake_scorer._record_audio
    original_index = local_wake_scorer._input_index
    try:
        local_wake_scorer._record_audio = fake_record
        local_wake_scorer._input_index = fake_index
        source = LocalWakeScorerTranscriptSource(
            threshold=0.7,
            listen_seconds=1,
            rest_seconds=0,
            max_wait_seconds=1,
        )
        source._load = lambda: None
        source._best_score = lambda audio: (0.9, audio)
        transcript = await source.listen()
        _require(transcript == "Maya", "wake scorer did not return wake transcript")
        _require(calls["record"] == 1, "wake scorer did not record exactly once")
    finally:
        local_wake_scorer._record_audio = original_record
        local_wake_scorer._input_index = original_index

    print("local_wake_scorer_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
