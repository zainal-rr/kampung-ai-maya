# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

import argparse
import time
import pickle
import tempfile
from pathlib import Path

import numpy as np
import sounddevice as sd
from openwakeword.utils import AudioFeatures
from scipy.io.wavfile import write as write_wav

from maya_core.wakeword_sample_scorer import clip_features
from maya_core.workspace_paths import workspace_dir


MODEL_PATH = Path.home() / "Desktop/Maya/artifacts/wakeword_models/maya_wake_scorer.pkl"


def main() -> None:
    args = _args()
    device = _input_index(args.device)
    scorer = pickle.load(MODEL_PATH.open("rb"))
    extractor = AudioFeatures(inference_framework="onnx", ncpu=1)
    best_score = 0.0
    best_audio: np.ndarray | None = None

    print(f"one_stage_wake: device={args.device} index={device}")
    print(f"one_stage_wake: duration={args.seconds}s threshold={args.threshold}")
    if args.ready_delay > 0:
        print(f"one_stage_wake: mic opens in {args.ready_delay}s")
        time.sleep(args.ready_delay)
    print("one_stage_wake: mic open, say a Maya wake phrase")
    full_audio = sd.rec(
        int(16000 * args.seconds),
        samplerate=16000,
        channels=1,
        dtype="int16",
        device=device,
    )
    sd.wait()
    full_audio = np.asarray(full_audio).reshape(-1).astype(np.int16)
    step = max(1, int(16000 * args.score_every))
    window = max(1, int(16000 * args.score_seconds))
    for start in range(0, max(1, full_audio.shape[0] - window + 1), step):
        audio = full_audio[start : start + window]
        if audio.shape[0] < window:
            audio = np.pad(audio, (0, window - audio.shape[0]))
        score = _score(audio, scorer, extractor)
        if score > best_score:
            best_score = score
            best_audio = audio.copy()
        print(f"one_stage_wake: score={score:.3f}")
        if score >= args.threshold:
            saved = _save_candidate(audio, score)
            print(f"one_stage_wake: detected score={score:.3f}")
            print(f"one_stage_wake: candidate={saved}")
            return
    print("one_stage_wake: not_detected")
    if best_audio is not None:
        saved = _save_candidate(best_audio, best_score)
        print(f"one_stage_wake: best_score={best_score:.3f}")
        print(f"one_stage_wake: best_candidate={saved}")


def _score(audio: np.ndarray, scorer, extractor: AudioFeatures) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.wav"
        write_wav(path, 16000, audio)
        features = clip_features(path, extractor)
    return float(scorer.predict_proba(features)[0][1])


def _save_candidate(audio: np.ndarray, score: float) -> Path:
    output_dir = workspace_dir("artifacts", create=True) / "wakeword_candidates"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"candidate_{int(time.time())}_{score:.3f}.wav"
    write_wav(path, 16000, audio)
    return path


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
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--score-seconds", type=float, default=2.0)
    parser.add_argument("--score-every", type=float, default=0.5)
    parser.add_argument("--ready-delay", type=float, default=0.0)
    return parser.parse_args()


if __name__ == "__main__":
    main()
