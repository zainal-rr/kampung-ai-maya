from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from maya_core.provenance import make_provenance
from maya_core.sounddevice_audio import resolve_sounddevice_input_after_refresh
from maya_meet.voiceprint import verify_voiceprint
from maya_meet.voiceprint_capture import AudioSample, SAMPLE_RATE, audio_quality, quality_stats, record_replay, record_usable_sample
from maya_meet.voiceprint_store import enroll_voiceprint, load_voiceprint


DEFAULT_MODEL = "speechbrain/spkrec-ecapa-voxceleb"


def main() -> None:
    parser = argparse.ArgumentParser(description="Enroll and evaluate Maya Meet owner voiceprint from local audio.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    enroll = sub.add_parser("enroll-live")
    enroll.add_argument("--samples", type=int, default=5)
    enroll.add_argument("--holdout-samples", type=int, default=4)
    enroll.add_argument("--negative-samples", type=int, default=0)
    enroll.add_argument("--seconds", type=float, default=4.0)
    enroll.add_argument("--long-test", action="store_true", help="Use longer samples and more holdouts for real enrollment evaluation.")
    enroll.add_argument("--device", default="")
    enroll.add_argument("--replay-output-device", default="")
    enroll.add_argument("--threshold", type=float, default=0.86)
    enroll.add_argument("--no-replay-check", action="store_true")
    enroll.add_argument("--yes-owner-channel", action="store_true", help="Required: confirms this is run from an owner-authenticated local channel.")
    enroll.add_argument("--scorecard", default="")
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(_safe_status(), indent=2, sort_keys=True))
        return
    if args.command == "enroll-live":
        if not args.yes_owner_channel:
            raise SystemExit("Refusing enrollment: pass --yes-owner-channel from the local owner-authenticated iMac session.")
        samples = max(args.samples, 7) if args.long_test else args.samples
        holdout_samples = max(args.holdout_samples, 6) if args.long_test else args.holdout_samples
        seconds = max(args.seconds, 8.0) if args.long_test else args.seconds
        if args.long_test:
            print(f"Long voiceprint test enabled: samples={samples}, holdouts={holdout_samples}, seconds={seconds:g}")
        result = enroll_live(
            samples=samples,
            holdout_samples=holdout_samples,
            negative_samples=args.negative_samples,
            seconds=seconds,
            device_name=args.device,
            replay_output_device_name=args.replay_output_device,
            threshold=args.threshold,
            replay_check=not args.no_replay_check,
            scorecard_path=Path(args.scorecard).expanduser() if args.scorecard else None,
        )
        print(json.dumps(result, indent=2, sort_keys=True))


def enroll_live(
    *,
    samples: int,
    holdout_samples: int,
    negative_samples: int,
    seconds: float,
    device_name: str,
    replay_output_device_name: str,
    threshold: float,
    replay_check: bool,
    scorecard_path: Path | None = None,
) -> dict[str, Any]:
    if samples < 3:
        raise ValueError("At least 3 enrollment samples are required.")
    if holdout_samples < 2:
        raise ValueError("At least 2 holdout samples are required.")
    device = resolve_sounddevice_input_after_refresh(device_name or None)
    classifier = _speaker_classifier()
    enrollment: list[AudioSample] = []
    holdout: list[AudioSample] = []
    negatives: list[AudioSample] = []
    print("Voiceprint enrollment. Speak naturally during each sample.")
    print("Suggested phrase: Maya, this is Zainal speaking in a meeting. Please verify my voice.")
    for index in range(samples):
        audio, quality = record_usable_sample(f"owner enrollment {index + 1}/{samples}", seconds=seconds, device=device)
        enrollment.append(AudioSample("owner_enrollment", audio, _embedding(classifier, audio), quality["rms"], quality["peak"]))
    for index in range(holdout_samples):
        audio, quality = record_usable_sample(f"owner holdout {index + 1}/{holdout_samples}", seconds=seconds, device=device)
        holdout.append(AudioSample("owner_holdout", audio, _embedding(classifier, audio), quality["rms"], quality["peak"]))
    for index in range(max(0, negative_samples)):
        print("For this sample, use a non-owner voice if available. If not, stop and rerun later with --negative-samples 0.")
        audio, quality = record_usable_sample(f"non-owner negative {index + 1}/{negative_samples}", seconds=seconds, device=device)
        negatives.append(AudioSample("negative", audio, _embedding(classifier, audio), quality["rms"], quality["peak"]))
    centroid = _centroid([sample.embedding for sample in enrollment])
    enrolled = enroll_voiceprint(
        owner_provenance=make_provenance("owner_voice"),
        embedding=centroid,
        threshold=threshold,
        sample_count=len(enrollment),
        metadata={
            "model": DEFAULT_MODEL,
            "sample_rate": SAMPLE_RATE,
            "seconds_per_sample": seconds,
            "holdout_samples": len(holdout),
            "negative_samples": len(negatives),
            "raw_audio_saved": False,
        },
    )
    stored = load_voiceprint()
    owner_scores = [_score(stored, sample.embedding) for sample in holdout]
    negative_scores = [_score(stored, sample.embedding) for sample in negatives]
    replay_scores: list[float] = []
    replay_quality: dict[str, float] | None = None
    if replay_check:
        replay_audio = record_replay(
            enrollment[0].audio,
            seconds=seconds,
            device=device,
            output_device_name=replay_output_device_name,
        )
        if replay_audio is not None:
            replay_quality = _audio_quality(replay_audio)
            replay_scores.append(_score(stored, _embedding(classifier, replay_audio)))
    scorecard = {
        "status": enrolled.status,
        "reason_code": enrolled.reason_code,
        "enrollment_id": enrolled.enrollment_id,
        "model": DEFAULT_MODEL,
        "threshold": threshold,
        "sample_rate": SAMPLE_RATE,
        "sample_counts": {
            "enrollment": len(enrollment),
            "owner_holdout": len(holdout),
            "negative": len(negatives),
            "recording_replay": len(replay_scores),
        },
        "scores": {
            "owner_holdout": _stats(owner_scores),
            "negative": _stats(negative_scores),
            "recording_replay": _stats(replay_scores),
        },
        "audio_quality": {
            "enrollment": quality_stats(enrollment, _stats),
            "owner_holdout": quality_stats(holdout, _stats),
            "negative": quality_stats(negatives, _stats),
            "recording_replay": replay_quality or {"count": 0},
        },
        "acceptance": _acceptance(owner_scores, negative_scores, replay_scores, threshold),
        "created_at": time.time(),
    }
    target = scorecard_path or Path("logs/live_tests") / f"meet_voiceprint_scorecard_{int(time.time())}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(scorecard, indent=2, sort_keys=True), "utf-8")
    print(f"Voiceprint scorecard written to {target}")
    return scorecard


def _safe_status() -> dict[str, Any]:
    payload = load_voiceprint()
    return {
        "status": payload.get("status") or "not_enrolled",
        "enrollment_id": payload.get("enrollment_id") or "",
        "threshold": payload.get("threshold") or "",
        "sample_count": payload.get("sample_count") or 0,
        "created_at": payload.get("created_at") or "",
        "metadata": payload.get("metadata") or {},
    }


def _speaker_classifier():
    from speechbrain.inference.speaker import EncoderClassifier

    savedir = Path.home() / "Library" / "Caches" / "Kampung AI" / "speechbrain_spkrec_ecapa_voxceleb"
    savedir.mkdir(parents=True, exist_ok=True)
    return EncoderClassifier.from_hparams(source=DEFAULT_MODEL, savedir=str(savedir))


def _embedding(classifier, audio: np.ndarray) -> list[float]:
    trimmed = _trim_or_pad(audio, min_seconds=1.5)
    wav = torch.tensor(trimmed, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        embedding = classifier.encode_batch(wav).squeeze().detach().cpu().numpy().astype(float)
    return [float(value) for value in embedding.reshape(-1)]


def _trim_or_pad(audio: np.ndarray, *, min_seconds: float) -> np.ndarray:
    clean = np.asarray(audio, dtype=np.float32).reshape(-1)
    if clean.size == 0:
        clean = np.zeros(int(SAMPLE_RATE * min_seconds), dtype=np.float32)
    clean = np.nan_to_num(clean)
    peak = float(np.max(np.abs(clean))) if clean.size else 0.0
    if peak > 1.0:
        clean = clean / peak
    min_len = int(SAMPLE_RATE * min_seconds)
    if clean.size < min_len:
        clean = np.pad(clean, (0, min_len - clean.size))
    return clean


def _centroid(embeddings: list[list[float]]) -> list[float]:
    matrix = np.asarray(embeddings, dtype=float)
    vector = matrix.mean(axis=0)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return [float(value) for value in vector.reshape(-1)]


def _score(enrollment: dict[str, Any], embedding: list[float]) -> float:
    return float(verify_voiceprint(enrollment, embedding).confidence)


def _stats(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {"count": 0}
    return {
        "count": len(clean),
        "min": min(clean),
        "max": max(clean),
        "mean": sum(clean) / len(clean),
        "values": clean,
    }


def _acceptance(owner_scores: list[float], negative_scores: list[float], replay_scores: list[float], threshold: float) -> dict[str, Any]:
    false_rejects = [score for score in owner_scores if score < threshold]
    false_accepts = [score for score in negative_scores if score >= threshold]
    replay_accepts = [score for score in replay_scores if score >= threshold]
    blockers: list[str] = []
    if false_rejects:
        blockers.append("owner_false_reject")
    if false_accepts:
        blockers.append("negative_false_accept")
    if replay_accepts:
        blockers.append("recording_replay_accept")
    if not negative_scores:
        blockers.append("negative_samples_missing")
    if not replay_scores:
        blockers.append("recording_replay_missing")
    return {
        "m2_enable_recommended": not blockers,
        "blockers": blockers,
        "false_reject_count": len(false_rejects),
        "false_accept_count": len(false_accepts),
        "recording_replay_accept_count": len(replay_accepts),
        "note": "M2 should remain disabled unless this is true and the live context still feels reliable.",
    }


if __name__ == "__main__":
    main()
