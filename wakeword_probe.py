import argparse
import time

import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from openwakeword.utils import download_models


def main() -> None:
    args = _args()
    device = sounddevice_input_index(args.device)
    download_models(model_names=[args.model])
    model = Model(wakeword_models=[args.model], inference_framework="onnx")
    best_score = 0.0
    best_label = ""
    detected_at = None

    print(f"wakeword_probe: device={args.device} index={device}")
    print(f"wakeword_probe: model={args.model} duration={args.seconds}s")
    print("wakeword_probe: speak the wake phrase now")

    start = time.time()
    with sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype="int16",
        blocksize=1280,
        device=device,
    ) as stream:
        while time.time() - start < args.seconds:
            audio, _ = stream.read(1280)
            scores = model.predict(np.squeeze(audio))
            label, score = max(scores.items(), key=lambda item: item[1])
            if score > best_score:
                best_label = label
                best_score = float(score)
            if score >= args.threshold and detected_at is None:
                detected_at = time.time() - start
                print(f"wakeword_probe: detected {label} score={score:.3f} at {detected_at:.2f}s")

    status = "detected" if detected_at is not None else "not_detected"
    print(f"wakeword_probe: status={status}")
    print(f"wakeword_probe: best={best_label} score={best_score:.3f}")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="Zainal’s Headphone")
    parser.add_argument("--model", default="hey_jarvis")
    parser.add_argument("--seconds", type=int, default=8)
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser.parse_args()


def sounddevice_input_index(name: str) -> int | None:
    if name.isdigit():
        return int(name)
    lowered = name.casefold()
    for index, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels", 0)) <= 0:
            continue
        if lowered in str(device.get("name", "")).casefold():
            return index
    return None


if __name__ == "__main__":
    main()
