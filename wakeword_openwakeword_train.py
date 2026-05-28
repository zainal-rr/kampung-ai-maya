from __future__ import annotations

import runpy
import sys


def main() -> None:
    import multiprocessing as mp

    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass
    import scipy.special

    if not hasattr(scipy.special, "sph_harm") and hasattr(scipy.special, "sph_harm_y"):
        scipy.special.sph_harm = scipy.special.sph_harm_y
    import torchaudio

    if not hasattr(torchaudio, "info"):
        import soundfile

        class AudioInfo:
            def __init__(self, path: str):
                info = soundfile.info(path)
                self.num_frames = info.frames
                self.sample_rate = info.samplerate
                self.num_channels = info.channels
                self.bits_per_sample = 16
                self.encoding = "PCM_S"

        torchaudio.info = AudioInfo
    sys.argv[0] = "openwakeword.train"
    runpy.run_module("openwakeword.train", run_name="__main__")


if __name__ == "__main__":
    main()
