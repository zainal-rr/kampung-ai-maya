from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import os

from sounddevice_audio import configured_output_names, resolve_first_output_name


def main() -> None:
    old_names = os.environ.get("IMAC_AUDIO_OUTPUT_NAMES")
    old_single = os.environ.get("IMAC_AUDIO_OUTPUT")
    try:
        os.environ["IMAC_AUDIO_OUTPUT_NAMES"] = "Definitely Missing Output"
        os.environ["IMAC_AUDIO_ALLOW_DEFAULT_OUTPUT_FALLBACK"] = "0"
        os.environ.pop("IMAC_AUDIO_OUTPUT", None)
        device, label = resolve_first_output_name()
        _require(device is None, "missing configured output should not fall back to default speaker")
        _require("Definitely Missing Output" in label, "missing output label not preserved")
        _require(configured_output_names() == ["Definitely Missing Output"], "configured output names not parsed")
    finally:
        _restore("IMAC_AUDIO_OUTPUT_NAMES", old_names)
        _restore("IMAC_AUDIO_OUTPUT", old_single)
        os.environ.pop("IMAC_AUDIO_ALLOW_DEFAULT_OUTPUT_FALLBACK", None)
    print("sounddevice_audio_smoke: ok")


def _restore(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
