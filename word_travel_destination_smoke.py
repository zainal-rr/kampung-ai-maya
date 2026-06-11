from __future__ import annotations

from word_quality_travel import destination_consistency_issue_details, travel_consistency_issues


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
    weak_wrong = travel_consistency_issues(
        "Seoul solo food trip for two days",
        [
            "This Tokyo food itinerary focuses on Shinjuku ramen and Tsukiji market.",
            "Use Suica and JR lines for the Japan route.",
        ],
        list(headings),
    )
    _require(not any("destination mismatch" in issue for issue in weak_wrong), f"open-world body mismatch should not hard-fail: {weak_wrong!r}")

    strong_wrong = travel_consistency_issues(
        "Seoul solo food trip for two days",
        [
            "This Tokyo food itinerary focuses on Shinjuku ramen and Tsukiji market.",
            "Use Suica and JR lines for the Japan route.",
        ],
        ["Tokyo Trip Overview", "Tokyo Day 1 Plan", "Tokyo Day 2 Plan"],
    )
    _require(any("destination mismatch" in issue for issue in strong_wrong), f"expected strong mismatch blocker, got {strong_wrong!r}")

    warnings = destination_consistency_issue_details(
        "Seoul solo food trip for two days",
        [
            "This Tokyo food itinerary focuses on Shinjuku ramen and Tsukiji market.",
            "Use Suica and JR lines for the Japan route.",
        ],
        list(headings),
    )
    _require(any(issue.severity == "warning" for issue in warnings), f"expected warning details for ambiguous mismatch, got {warnings!r}")

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
