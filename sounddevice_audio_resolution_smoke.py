from __future__ import annotations

import os

import sounddevice_audio as audio


class FakeSd:
    def __init__(self, default_output=1):
        self.default = type("Default", (), {"device": [0, default_output]})()
        self.terminated = 0
        self.initialized = 0

    def query_devices(self):
        return [
            {"name": "Zainal’s Headphone", "max_input_channels": 1, "max_output_channels": 0},
            {"name": "Zainal’s Headphone", "max_input_channels": 0, "max_output_channels": 2},
            {"name": "iMac Speakers", "max_input_channels": 0, "max_output_channels": 2},
        ]

    def _terminate(self):
        self.terminated += 1

    def _initialize(self):
        self.initialized += 1


def main() -> None:
    old = audio.sd
    try:
        audio.sd = FakeSd()
        _require(audio.resolve_sounddevice_output("Zainal's Headphone") == 1, "straight apostrophe did not match")
        _require(audio.resolve_sounddevice_output("Zainal’s Headphone") == 1, "curly apostrophe did not match")
        os.environ["IMAC_AUDIO_OUTPUT_NAMES"] = "Definitely Missing Output"
        os.environ["IMAC_AUDIO_ALLOW_DEFAULT_OUTPUT_FALLBACK"] = "1"
        _require(audio.resolve_first_output_name()[0] == 1, "first output default fallback failed")
        _require(audio.resolve_default_output()[0] == 1, "default output index fallback failed")
        audio.sd = FakeSd(default_output=2)
        result = audio.resolve_first_output()
        _require(result.device == 2, "speaker fallback device not returned")
        _require(result.used_default_fallback, "default fallback was not marked")
        _require(result.missing_configured == ("Definitely Missing Output",), "missing configured output not tracked")
        _require("iMac Speakers" in result.label, "speaker fallback label not preserved")
        audio.sd = RecoveringFakeSd()
        os.environ["IMAC_AUDIO_OUTPUT_NAMES"] = "Zainal’s Headphone"
        result = audio.resolve_first_output()
        _require(result.device == 1, "PortAudio refresh did not recover configured output")
        _require(not result.used_default_fallback, "recovered output should not be marked as fallback")
    finally:
        audio.sd = old
        os.environ.pop("IMAC_AUDIO_OUTPUT_NAMES", None)
        os.environ.pop("IMAC_AUDIO_ALLOW_DEFAULT_OUTPUT_FALLBACK", None)
    print("sounddevice_audio_resolution_smoke: ok")


class RecoveringFakeSd(FakeSd):
    def __init__(self):
        super().__init__(default_output=2)
        self.recovered = False

    def query_devices(self):
        if not self.recovered:
            return [
                {"name": "iMac Speakers", "max_input_channels": 0, "max_output_channels": 2},
            ]
        return super().query_devices()

    def _initialize(self):
        super()._initialize()
        self.recovered = True


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
