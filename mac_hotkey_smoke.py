from __future__ import annotations

from mac_hotkey import OPTION_KEY, parse_hotkey


def main() -> None:
    start = parse_hotkey("<alt>+<space>")
    stop = parse_hotkey("<alt>+<esc>")
    assert start.key_code == 49
    assert start.modifiers == OPTION_KEY
    assert stop.key_code == 53
    assert stop.modifiers == OPTION_KEY
    print("mac_hotkey_smoke: ok")


if __name__ == "__main__":
    main()
