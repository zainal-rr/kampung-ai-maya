import json
import pickle
import re
from pathlib import Path

import numpy as np
from openwakeword.utils import AudioFeatures
from scipy.io import wavfile
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from maya_core.workspace_paths import workspace_dir


SAMPLE_ROOT = workspace_dir("artifacts", create=True) / "wakeword_samples"
MODEL_DIR = workspace_dir("artifacts", create=True) / "wakeword_models"


def main() -> None:
    positive = sorted((SAMPLE_ROOT / "positive").glob("*.wav"))
    negative = sorted((SAMPLE_ROOT / "negative").glob("*.wav"))
    paths = positive + negative
    labels = np.array([1] * len(positive) + [0] * len(negative))
    extractor = AudioFeatures(inference_framework="onnx", ncpu=1)
    features = np.vstack([clip_features(path, extractor) for path in paths])
    weights = np.array([sample_weight(path, label) for path, label in zip(paths, labels)])
    scores = leave_one_out_scores(features, labels, weights)
    report = {
        "positive_count": len(positive),
        "negative_count": len(negative),
        "threshold_sweep": threshold_sweep(labels, scores),
        "errors_at_0_8": sample_errors(paths, labels, scores, 0.8),
    }
    clf = classifier()
    clf.fit(features, labels, logisticregression__sample_weight=weights)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "maya_wake_weighted_scorer.pkl"
    with model_path.open("wb") as handle:
        pickle.dump(clf, handle)
    report["model_path"] = str(model_path)
    out = MODEL_DIR / "maya_wake_weighted_scorer_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def classifier():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.18))


def sample_weight(path: Path, label: int) -> float:
    if label == 1:
        return 1.0
    timestamp = extract_timestamp(path)
    if timestamp >= 1779468680:
        return 2.0
    hard_false_wake = {
        "negative_1779463544_03.wav",
        "negative_1779463552_05.wav",
        "negative_1779465382_05.wav",
        "negative_1779468139_02.wav",
        "negative_1779468180_09.wav",
        "negative_1779468691_03.wav",
        "negative_1779468795_07.wav",
    }
    if path.name in hard_false_wake:
        return 6.0
    return 1.5


def extract_timestamp(path: Path) -> int:
    match = re.search(r"_(\d+)_", path.name)
    return int(match.group(1)) if match else 0


def leave_one_out_scores(features: np.ndarray, labels: np.ndarray, weights: np.ndarray) -> np.ndarray:
    scores = []
    for train, test in LeaveOneOut().split(features):
        clf = classifier()
        clf.fit(features[train], labels[train], logisticregression__sample_weight=weights[train])
        scores.append(float(clf.predict_proba(features[test])[0, 1]))
    return np.array(scores)


def clip_features(path: Path, extractor: AudioFeatures) -> np.ndarray:
    sample_rate, audio = wavfile.read(path)
    if sample_rate != 16000:
        raise ValueError(f"Expected 16000 Hz: {path}")
    audio = np.asarray(audio).reshape(-1).astype(np.int16)
    target = 16000 * 3
    if audio.shape[0] < target:
        audio = np.pad(audio, (0, target - audio.shape[0]))
    else:
        audio = audio[:target]
    embeddings = extractor.embed_clips(audio[None, :], batch_size=1, ncpu=1)[0]
    return np.concatenate([embeddings.mean(axis=0), embeddings.std(axis=0), embeddings.max(axis=0)])[None, :]


def threshold_sweep(labels: np.ndarray, scores: np.ndarray) -> list[dict[str, float | int]]:
    rows = []
    for threshold in [0.5, 0.6, 0.7, 0.8, 0.9]:
        predictions = (scores >= threshold).astype(int)
        tn, fp, fn, tp = [int(value) for value in confusion_matrix(labels, predictions, labels=[0, 1]).ravel()]
        rows.append({
            "threshold": threshold,
            "accuracy": float(accuracy_score(labels, predictions)),
            "false_wakes": fp,
            "missed_wakes": fn,
            "true_wakes": tp,
            "true_negatives": tn,
        })
    return rows


def sample_errors(paths: list[Path], labels: np.ndarray, scores: np.ndarray, threshold: float) -> list[dict[str, str | float | int]]:
    predictions = (scores >= threshold).astype(int)
    return [
        {"path": str(path), "label": int(label), "prediction": int(prediction), "score": float(score)}
        for path, label, score, prediction in zip(paths, labels, scores, predictions)
        if int(label) != int(prediction)
    ]


if __name__ == "__main__":
    main()
