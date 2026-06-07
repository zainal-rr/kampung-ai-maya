from __future__ import annotations

from word_quality_travel import travel_consistency_issues


def main() -> None:
    headings = (
        "Trip Overview",
        "Day 1 Plan",
        "Day 2 Plan",
        "Food And Restaurant Highlights",
        "Budget Notes",
        "Booking And Transit Notes",
        "Recommendations",
    )
    wrong = travel_consistency_issues(
        "Seoul solo food trip for two days",
        [
            "This Tokyo food itinerary focuses on Shinjuku ramen and Tsukiji market.",
            "Use Suica and JR lines for the Japan route.",
        ],
        list(headings),
    )
    _require(any("destination mismatch" in issue for issue in wrong), f"expected mismatch, got {wrong!r}")

    right = travel_consistency_issues(
        "Seoul solo food trip for two days",
        [
            "This Seoul food itinerary focuses on Myeongdong, Gwangjang Market, and Seongsu cafes.",
            "Use T-money and Naver Maps for local movement.",
        ],
        list(headings),
    )
    _require(not any("destination" in issue for issue in right), f"expected no destination issue, got {right!r}")
    print("word_travel_destination_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
