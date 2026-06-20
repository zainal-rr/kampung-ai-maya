import argparse
import json
import time
from pathlib import Path

import sounddevice as sd
from scipy.io.wavfile import write as write_wav

from maya_core.workspace_paths import workspace_dir


def main() -> None:
    args = _args()
    root = workspace_dir("artifacts", create=True) / "wakeword_samples"
    output_dir = root / args.label
    output_dir.mkdir(parents=True, exist_ok=True)
    device = _input_index(args.device)
    metadata = []

    print(f"wakeword_sample_recorder: device={args.device} index={device}")
    print(f"wakeword_sample_recorder: saving to {output_dir}")
    for number in range(1, args.count + 1):
        print(f"sample {number}/{args.count}: {args.prompt}")
        time.sleep(args.ready_delay)
        audio = sd.rec(
            int(args.seconds * args.sample_rate),
            samplerate=args.sample_rate,
            channels=1,
            dtype="int16",
            device=device,
        )
        sd.wait()
        path = output_dir / f"{args.label}_{int(time.time())}_{number:02d}.wav"
        write_wav(path, args.sample_rate, audio)
        metadata.append(
            {
                "path": str(path),
                "label": args.label,
                "prompt": args.prompt,
                "device": args.device,
                "seconds": args.seconds,
                "sample_rate": args.sample_rate,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        print(f"saved {path}")
        time.sleep(args.gap)

    meta_path = output_dir / "metadata.jsonl"
    with meta_path.open("a", encoding="utf-8") as handle:
        for item in metadata:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"metadata {meta_path}")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", choices=["positive", "negative"], required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--device", default="Zainal’s Headphone")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--ready-delay", type=float, default=1.0)
    parser.add_argument("--gap", type=float, default=0.5)
    return parser.parse_args()


def _input_index(name: str) -> int | None:
    if name.isdigit():
        return int(name)
    lowered = name.casefold()
    for index, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels", 0)) <= 0:
            continue
        if lowered in str(device.get("name", "")).casefold():
            return index
    raise ValueError(f"Input device not found: {name}")


if __name__ == "__main__":
    main()
