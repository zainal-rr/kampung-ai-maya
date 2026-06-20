from __future__ import annotations

import json
import os
import shutil
import urllib.request
from pathlib import Path

import yaml


ROOT = Path.home() / "Desktop" / "Maya" / "artifacts" / "wakeword_official"
VOICE_DIR = ROOT / "voices"
SHIM_DIR = ROOT / "piper_generator_shim"
DATA_DIR = ROOT / "data"
MODEL_NAME = "maya_wake_official_tiny"


VOICE_URLS = {
    "en_US-lessac-medium.onnx": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
        "en/en_US/lessac/medium/en_US-lessac-medium.onnx?download=true"
    ),
    "en_US-lessac-medium.onnx.json": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
        "en/en_US/lessac/medium/en_US-lessac-medium.onnx.json?download=true"
    ),
}


def ensure_dirs() -> None:
    for path in [
        VOICE_DIR,
        SHIM_DIR,
        DATA_DIR / "background",
        DATA_DIR / "false_positive_features",
        ROOT / "outputs",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def download_voices() -> None:
    for name, url in VOICE_URLS.items():
        dest = VOICE_DIR / name
        if dest.exists() and dest.stat().st_size > 1024:
            continue
        urllib.request.urlretrieve(url, dest)


def write_generator_shim() -> Path:
    shim = SHIM_DIR / "generate_samples.py"
    model = VOICE_DIR / "en_US-lessac-medium.onnx"
    shim.write_text(
        f"""
from pathlib import Path
import itertools as it
import wave
import tempfile
import numpy as np
from piper import PiperVoice, SynthesisConfig
from scipy.io import wavfile
from scipy.signal import resample_poly

MODEL = Path({str(model)!r})


def generate_samples(text, output_dir, max_samples=None, file_names=None, batch_size=1,
                     length_scales=(0.75, 1.0, 1.25), noise_scales=(0.667,),
                     noise_scale_ws=(0.8,), **kwargs):
    if max_samples is None:
        max_samples = len(text) if isinstance(text, list) else 1
    voice = PiperVoice.load(MODEL, use_cuda=False)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    texts = it.cycle(text if isinstance(text, list) else [text])
    names = it.cycle(file_names) if file_names else None
    settings = it.cycle(it.product(length_scales, noise_scales, noise_scale_ws))
    for idx in range(max_samples):
        length_scale, noise_scale, noise_w_scale = next(settings)
        name = next(names) if names else f"{{idx}}.wav"
        final_path = Path(output_dir) / name
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            with wave.open(tmp.name, "wb") as wav_file:
                voice.synthesize_wav(
                    next(texts),
                    wav_file=wav_file,
                    syn_config=SynthesisConfig(
                        length_scale=length_scale,
                        noise_scale=noise_scale,
                        noise_w_scale=noise_w_scale,
                    ),
                )
            sr, data = wavfile.read(tmp.name)
        if sr != 16000:
            data = resample_poly(data.astype(np.float32), 16000, sr)
        data = np.clip(data, -32768, 32767).astype(np.int16)
        wavfile.write(final_path, 16000, data)
""".lstrip(),
        encoding="utf-8",
    )
    return shim


def copy_local_background() -> None:
    src = Path.home() / "Desktop" / "Maya" / "artifacts" / "wakeword_samples" / "negative"
    dest = DATA_DIR / "background"
    if src.exists():
        for wav in src.glob("*.wav"):
            target = dest / wav.name
            if not target.exists():
                shutil.copy2(wav, target)
    if not any(dest.glob("*.wav")):
        silence = dest / "silence.wav"
        import numpy as np
        from scipy.io import wavfile

        wavfile.write(silence, 16000, np.zeros(32000, dtype=np.int16))


def write_false_positive_features() -> Path:
    output = DATA_DIR / "false_positive_features" / "false_positive_features.npy"
    if output.exists():
        return output
    import numpy as np
    from openwakeword.utils import AudioFeatures
    from scipy.io import wavfile

    clips = []
    for wav in sorted((DATA_DIR / "background").glob("*.wav"))[:10]:
        sr, data = wavfile.read(wav)
        if sr != 16000:
            continue
        if data.ndim > 1:
            data = data[:, 0]
        if len(data) < 32000:
            data = np.pad(data, (0, 32000 - len(data)))
        clips.append(data[:32000].astype(np.int16))
    if not clips:
        clips.append(np.zeros(32000, dtype=np.int16))
    features = AudioFeatures(device="cpu").embed_clips(np.array(clips), batch_size=4)
    np.save(output, np.vstack(features))
    return output


def write_config(false_positive_path: Path) -> Path:
    import piper_sample_generator

    config = {
        "piper_sample_generator_path": str(SHIM_DIR),
        "output_dir": str(ROOT / "outputs"),
        "model_name": MODEL_NAME,
        "target_phrase": ["hey maya", "maya"],
        "rir_paths": [str(Path(piper_sample_generator.__file__).parent / "impulses")],
        "background_paths": [str(DATA_DIR / "background")],
        "background_paths_duplication_rate": [1],
        "n_samples": 24,
        "n_samples_val": 12,
        "tts_batch_size": 4,
        "custom_negative_phrases": ["may", "mayer", "hey may", "maya no", "my air"],
        "augmentation_rounds": 1,
        "augmentation_batch_size": 8,
        "feature_data_files": {},
        "false_positive_validation_data_path": str(false_positive_path),
        "batch_n_per_class": 16,
        "steps": 60,
        "max_negative_weight": 50,
        "target_false_positives_per_hour": 0.5,
        "model_type": "dnn",
        "layer_size": 64,
    }
    path = ROOT / "maya_wake_official_tiny.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def main() -> None:
    ensure_dirs()
    download_voices()
    write_generator_shim()
    copy_local_background()
    false_positive_path = write_false_positive_features()
    config = write_config(false_positive_path)
    report = {
        "root": str(ROOT),
        "config": str(config),
        "model_name": MODEL_NAME,
        "status": "prepared",
    }
    (ROOT / "prepare_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
