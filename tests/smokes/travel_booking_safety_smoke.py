from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from datetime import date

from maya_travel.flight_search_models import FieldAttempt, FlightDetails
from maya_travel.flight_search_reply import _filled_reply
from maya_travel.stay_booking_runtime import stay_reply
from maya_travel.travel_booking_safety import travel_booking_boundary_reply, travel_booking_safety_footer


class FakeDetails:
    location = "Kyoto"
    checkin = date(2026, 8, 30)
    checkout = date(2026, 9, 4)
    adults = 1
    rooms = 1
    assumptions = ()


class FakeStayResult:
    provider = "Booking.com"
    url = "https://www.booking.com/searchresults.html?ss=Kyoto"
    title = "Booking.com Kyoto"
    visible_text = "Kyoto hotel MYR 500"
    details = FakeDetails()
    options = ("Hotel A | MYR 500", "Hotel B | MYR 650")

    def verified(self) -> bool:
        return True


def main() -> None:
    footer = travel_booking_safety_footer(2)
    _require("exact option number or name" in footer, "footer missing exact-choice step")
    _require("explicit final confirmation" in footer, "footer missing final confirmation")
    _require("passport" in footer and "OTP" in footer, "footer missing sensitive-data boundary")

    blocked = travel_booking_boundary_reply("book this hotel with my card 4111111111111111")
    _require(blocked and "can't expose sensitive" in blocked.lower(), "sensitive travel request not blocked")
    private_submit = travel_booking_boundary_reply("submit my passport and card for this booking")
    _require(private_submit and "can't expose sensitive" in private_submit.lower(), "passport/card submit not hard blocked")
    staged = travel_booking_boundary_reply("book option 2")
    _require(staged and "have not booked anything" in staged, "exact-option booking should remain staged")

    flight_reply = _filled_reply(
        FlightDetails("Kuala Lumpur", "Penang", "June 7", "", True, (), ()),
        [FieldAttempt("destination", "Penang", "verified"), FieldAttempt("departure", "June 7", "verified")],
        ["Option 1 | MYR 300", "Option 2 | MYR 450"],
        "Google Flights | https://www.google.com/travel/flights",
    )
    _require("exact option number or name" in flight_reply, "flight reply missing staged safety")

    stay_text = stay_reply(FakeStayResult())
    _require("explicit final confirmation" in stay_text, "stay reply missing final confirmation")
    print("travel_booking_safety_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
