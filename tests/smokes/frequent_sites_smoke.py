from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
from pathlib import Path

from maya_browser.browser_capability import route_browser_capability, run_browser_capability
from maya_core.frequent_sites import find_frequent_site_request, frequent_site_catalog
from storage import get_preference, init_db


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)


async def main() -> None:
    _require(find_frequent_site_request("open github").site.id == "github", "GitHub frequent site missing")
    _require(find_frequent_site_request("open maybank").site.id == "maybank", "Maybank frequent site missing")
    _require(find_frequent_site_request("open google cloud console").site.id == "gcp_console", "GCP Console frequent site missing")
    _require(find_frequent_site_request("open airbnb").site.id == "airbnb", "Airbnb frequent site missing")

    _require(route_browser_capability("open github").child_skill == "frequent_site_open", "GitHub should open through frequent site")
    _require(route_browser_capability("open maybank").site_category == "sensitive_finance", "Maybank should be sensitive")
    _require(route_browser_capability("open airbnb").child_skill == "frequent_site_open", "Bare Airbnb should open site, not start a stay search")
    _require(route_browser_capability("find Airbnb in Penang").child_skill == "airbnb_stay_search", "Airbnb search should stay specialized")
    _require(route_browser_capability("find hotel in Penang").child_skill == "booking_com_hotel_search", "Hotel search should stay specialized")
    _require(route_browser_capability("google pokemon").child_skill == "google_search", "Google query should use Google Search skill")
    _require(route_browser_capability("google images modern kampung house").child_skill == "google_images", "Google Images route regressed")

    catalog = frequent_site_catalog()
    categories = {item["category"] for item in catalog}
    _require({"travel", "ai_dev", "research", "local_dashboard", "sensitive_finance"} <= categories, "frequent site categories missing")

    with tempfile.TemporaryDirectory(prefix="maya-frequent-sites-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()

        reply = await run_browser_capability(db_path, "open github", bridge=bridge)
        _require(bridge.urls[-1] == "https://github.com", "GitHub URL not opened")
        _require("GitHub" in reply, "GitHub reply missing")
        active = await get_preference(db_path, "maya_active_workflow")
        _require(active == "browser:site:github:https://github.com", "frequent site workflow not saved")

        reply = await run_browser_capability(db_path, "open maybank", bridge=bridge)
        _require(bridge.urls[-1] == "https://www.maybank2u.com.my", "Maybank URL not opened")
        _require("Sensitive mode is active" in reply, "Maybank sensitive boundary missing")
        _require("never read, fill, reveal, submit, or store" in reply, "Maybank hard boundary missing")

    print("frequent_sites_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
