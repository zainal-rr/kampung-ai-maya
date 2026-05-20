from __future__ import annotations

from imac_voice_policy import decide_imac_voice_route


def main() -> None:
    _expect("hello maya how are you", "grok")
    _expect("apa khabar", "grok")
    _expect("karang satu cerita pendek in Manglish", "gemini", filler=True)
    _expect("jawab in Manglish yang natural", "gemini", filler=True)
    _expect("remember my Malay style preference", "gemini", filler=True)
    _expect("architecture strategy", "grok")
    _expect("this is complex, make a plan for architecture strategy", "assistant")
    print("imac_voice_policy_smoke: ok")


def _expect(text: str, route: str, filler: bool = False) -> None:
    decision = decide_imac_voice_route(text)
    if decision.route != route:
        raise AssertionError(f"{text!r} routed to {decision.route}, expected {route}")
    if filler and not decision.filler:
        raise AssertionError(f"{text!r} should have a filler")


if __name__ == "__main__":
    main()
