import json
import pickle
from pathlib import Path

import numpy as np
from openwakeword.utils import AudioFeatures
from scipy.io import wavfile
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from maya_core.workspace_paths import workspace_dir


SAMPLE_ROOT = workspace_dir("artifacts", create=True) / "wakeword_samples"
MODEL_DIR = workspace_dir("artifacts", create=True) / "wakeword_models"


def main() -> None:
    positive = sorted((SAMPLE_ROOT / "positive").glob("*.wav"))
    negative = sorted((SAMPLE_ROOT / "negative").glob("*.wav"))
    if len(positive) < 5 or len(negative) < 5:
        raise ValueError("Need at least 5 positive and 5 negative samples.")

    extractor = AudioFeatures(inference_framework="onnx", ncpu=1)
    paths = positive + negative
    labels = np.array([1] * len(positive) + [0] * len(negative))
    features = np.vstack([clip_features(path, extractor) for path in paths])
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.25))
    scores = cross_val_predict(clf, features, labels, cv=LeaveOneOut(), method="predict_proba")[:, 1]
    predictions = (scores >= 0.5).astype(int)
    accuracy = float(accuracy_score(labels, predictions))
    matrix = confusion_matrix(labels, predictions, labels=[0, 1]).tolist()

    clf.fit(features, labels)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "maya_wake_scorer.pkl"
    report_path = MODEL_DIR / "maya_wake_scorer_report.json"
    with model_path.open("wb") as handle:
        pickle.dump(clf, handle)
    report = {
        "positive_count": len(positive),
        "negative_count": len(negative),
        "leave_one_out_accuracy": accuracy,
        "confusion_matrix_labels": ["negative", "positive"],
        "confusion_matrix": matrix,
        "threshold_sweep": threshold_sweep(labels, scores),
        "errors_at_0_6": sample_errors(paths, labels, scores, threshold=0.6),
        "model_path": str(model_path),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


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
    return np.concatenate(
        [
            embeddings.mean(axis=0),
            embeddings.std(axis=0),
            embeddings.max(axis=0),
        ]
    )[None, :]


def threshold_sweep(labels: np.ndarray, scores: np.ndarray) -> list[dict[str, float | int]]:
    rows = []
    for threshold in [0.5, 0.6, 0.7, 0.8, 0.9]:
        predictions = (scores >= threshold).astype(int)
        matrix = confusion_matrix(labels, predictions, labels=[0, 1])
        tn, fp, fn, tp = [int(value) for value in matrix.ravel()]
        rows.append(
            {
                "threshold": threshold,
                "accuracy": float(accuracy_score(labels, predictions)),
                "false_wakes": fp,
                "missed_wakes": fn,
                "true_wakes": tp,
                "true_negatives": tn,
            }
        )
    return rows


def sample_errors(paths: list[Path], labels: np.ndarray, scores: np.ndarray, threshold: float) -> list[dict[str, str | float | int]]:
    errors = []
    predictions = (scores >= threshold).astype(int)
    for path, label, score, prediction in zip(paths, labels, scores, predictions):
        if int(label) == int(prediction):
            continue
        errors.append(
            {
                "path": str(path),
                "label": int(label),
                "prediction": int(prediction),
                "score": float(score),
            }
        )
    return errors


if __name__ == "__main__":
    main()
