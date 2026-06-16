from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import tempfile
from pathlib import Path

from artisan_app_qa import qa_artisan_app_project


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artisan-app-qa-") as tmp:
        root = Path(tmp)
        app = root / "habit-app"
        app.mkdir()
        (app / "index.html").write_text(
            """<!doctype html>
<html><head><link rel="stylesheet" href="style.css"></head>
<body><h1>Daily Habits</h1><button>Water</button><button>Reading</button><button>Walking</button>
<script src="script.js"></script></body></html>
""",
            encoding="utf-8",
        )
        (app / "style.css").write_text("body { font-family: system-ui; }\n", encoding="utf-8")
        (app / "script.js").write_text("localStorage.setItem('smoke', 'ok');\n", encoding="utf-8")
        (app / "README.md").write_text("# Daily Habits\n\nOpen `index.html` in a browser.\n", encoding="utf-8")
        result = qa_artisan_app_project(
            root,
            request="build a daily habit tracker app. It should track water, reading, and walking.",
            changed_files=["habit-app/index.html", "habit-app/style.css", "habit-app/script.js"],
        )
        _require(result.passed, result.summary + " " + "; ".join(result.issues))
        _require(result.readme_path.endswith("README.md"), "README path missing from QA")

        (app / "index.html").write_text(
            """<!doctype html><html><head><script src="missing.js"></script></head><body>Water</body></html>""",
            encoding="utf-8",
        )
        failed = qa_artisan_app_project(root, request="track water, reading, and walking")
        _require(not failed.passed and any("missing linked asset" in issue for issue in failed.issues), "missing asset was not rejected")
    print("artisan_app_qa_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
