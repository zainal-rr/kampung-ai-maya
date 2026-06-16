# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

import argparse
import os
import pickle
import tempfile
import time
from collections import deque
from pathlib import Path

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from openwakeword.utils import AudioFeatures
from scipy.io.wavfile import write as write_wav

from maya_core.activation import split_wake_phrase
from wakeword_sample_scorer import clip_features
from xai_stt import xai_transcribe_file


MODEL_PATH = Path.home() / "Desktop/Maya/artifacts/wakeword_models/maya_wake_scorer.pkl"


def main() -> None:
    load_dotenv(".env")
    args = _args()
    device = _input_index(args.device)
    scorer = pickle.load(MODEL_PATH.open("rb"))
    extractor = AudioFeatures(inference_framework="onnx", ncpu=1)
    ring: deque[np.ndarray] = deque(maxlen=int(args.confirm_seconds / args.block_seconds))
    score_blocks = int(args.score_seconds / args.block_seconds)
    next_score_at = 0.0

    print(f"two_stage_wake: device={args.device} index={device}")
    print(f"two_stage_wake: duration={args.seconds}s threshold={args.threshold}")
    print("two_stage_wake: say Hey Maya, Maya, Hello Maya, or Good morning Maya")
    start = time.time()
    with sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype="int16",
        blocksize=int(16000 * args.block_seconds),
        device=device,
    ) as stream:
        while time.time() - start < args.seconds:
            block, _ = stream.read(int(16000 * args.block_seconds))
            ring.append(np.asarray(block).reshape(-1).astype(np.int16))
            if len(ring) < ring.maxlen or time.time() < next_score_at:
                continue
            next_score_at = time.time() + args.score_every
            confirm_audio = np.concatenate(list(ring))
            score_audio = np.concatenate(list(ring)[-score_blocks:])
            score = _score(score_audio, scorer, extractor)
            print(f"two_stage_wake: stage1 score={score:.3f}")
            if score < args.threshold:
                continue
            transcript = _confirm(confirm_audio, args.language)
            print(f"two_stage_wake: stage2 transcript={transcript!r}")
            woke, command = split_wake_phrase(transcript)
            if woke:
                print(f"two_stage_wake: confirmed command={command!r}")
                return
            print("two_stage_wake: rejected by stage2")
    print("two_stage_wake: not_detected")


def _score(audio: np.ndarray, scorer, extractor: AudioFeatures) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.wav"
        write_wav(path, 16000, audio)
        features = clip_features(path, extractor)
    return float(scorer.predict_proba(features)[0][1])


def _confirm(audio: np.ndarray, language: str) -> str:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("XAI_API_KEY is required for stage2 confirmation.")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wake_candidate.wav"
        write_wav(path, 16000, audio)
        return xai_transcribe_file(api_key, path, language)


def _input_index(name: str) -> int | None:
    if name.isdigit():
        return int(name)
    lowered = name.casefold()
    for index, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels", 0)) > 0:
            if lowered in str(device.get("name", "")).casefold():
                return index
    raise ValueError(f"Input device not found: {name}")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="Zainal’s Headphone")
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--threshold", type=float, default=0.65)
    parser.add_argument("--score-seconds", type=float, default=2.0)
    parser.add_argument("--confirm-seconds", type=float, default=3.0)
    parser.add_argument("--block-seconds", type=float, default=0.25)
    parser.add_argument("--score-every", type=float, default=0.5)
    parser.add_argument("--language", default="en")
    return parser.parse_args()


if __name__ == "__main__":
    main()
