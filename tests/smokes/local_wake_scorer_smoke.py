import asyncio

import numpy as np

import local_wake_scorer
from local_wake_scorer import LocalWakeScorerTranscriptSource


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
