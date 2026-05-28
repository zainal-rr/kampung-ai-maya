from voice_device_policy import local_wake_allowed, voice_intent_label


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    _require(
        local_wake_allowed("Zainal’s Headphone", "Zainal’s Headphone"),
        "Sony headphone intent should allow local wake",
    )
    _require(
        local_wake_allowed("Sony WH-1000XM5", "Sony WH-1000XM5"),
        "Sony XM5 name should allow local wake",
    )
    _require(not local_wake_allowed("AirPods Pro", "AirPods Pro"), "AirPods should not allow local wake")
    _require(not local_wake_allowed("iMac Microphone", "iMac Speakers"), "iMac audio should not allow local wake")
    _require(
        voice_intent_label("Zainal’s Headphone", "") == "sony_headphone_maya",
        "Sony headphone label should be Maya mode",
    )
    _require(voice_intent_label("AirPods Pro", "") == "no_voice_wake", "AirPods label should be no wake")
    print("voice_device_policy_smoke: ok")


if __name__ == "__main__":
    main()
