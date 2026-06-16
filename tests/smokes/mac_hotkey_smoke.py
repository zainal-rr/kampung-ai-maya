from __future__ import annotations

import mac_hotkey
from mac_hotkey import OPTION_KEY, CarbonHotKeyListener, parse_hotkey


def main() -> None:
    start = parse_hotkey("<alt>+<space>")
    stop = parse_hotkey("<alt>+<esc>")
    assert start.key_code == 49
    assert start.modifiers == OPTION_KEY
    assert stop.key_code == 53
    assert stop.modifiers == OPTION_KEY
    calls = []
    original_stop = mac_hotkey.CORE_FOUNDATION.CFRunLoopStop
    try:
        mac_hotkey.CORE_FOUNDATION.CFRunLoopStop = calls.append
        listener = CarbonHotKeyListener({})
        listener.run_loop = object()
        listener.stop()
        assert calls == []
    finally:
        mac_hotkey.CORE_FOUNDATION.CFRunLoopStop = original_stop
    print("mac_hotkey_smoke: ok")


if __name__ == "__main__":
    main()
