from __future__ import annotations

import html
import os
import re
import shutil
import threading
import tempfile
import urllib.request
from dataclasses import dataclass, asdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from maya_core.execution_broker import CommandSpec, run_command


@dataclass(frozen=True)
class ArtisanAppQaResult:
    passed: bool
    app_root: str
    summary: str
    issues: list[str]
    warnings: list[str]
    checks: list[str]
    preview_path: str = ""
    readme_path: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def qa_artisan_app_project(
    cwd: str | Path,
    *,
    request: str = "",
    brief: str = "",
    changed_files: list[str] | None = None,
) -> ArtisanAppQaResult:
    root = Path(cwd).expanduser()
    app_root = _select_app_root(root, changed_files or [])
    issues: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []
    if app_root is None:
        return ArtisanAppQaResult(False, str(root), "No index.html found.", ["missing index.html"], warnings, checks)

    index = app_root / "index.html"
    text = _read(index)
    if "<!doctype html" not in text.lower() and "<html" not in text.lower():
        issues.append("index.html does not look like a complete HTML document")
    checks.append("index.html found")

    linked = _linked_assets(text)
    for asset in linked:
        if _is_external(asset):
            warnings.append(f"external asset reference: {asset}")
            continue
        if not (app_root / asset).exists():
            issues.append(f"missing linked asset: {asset}")
    if linked:
        checks.append(f"linked assets checked: {len(linked)}")

    css_files = sorted({app_root / item for item in linked if item.endswith(".css")} | set(app_root.rglob("*.css")))
    for css in css_files:
        if not css.exists() or "node_modules" in css.parts:
            continue
        css_issue = _css_quality_issue(css)
        if css_issue:
            issues.append(f"CSS quality failed in {css.relative_to(app_root)}: {css_issue}")
        else:
            checks.append(f"CSS checked {css.relative_to(app_root)}")

    js_files = sorted({app_root / item for item in linked if item.endswith(".js")} | set(app_root.rglob("*.js")))
    node = shutil.which("node")
    for js in js_files:
        if not js.exists() or "node_modules" in js.parts:
            continue
        if node:
            proc = run_command(CommandSpec(
                argv=(node, "--check", str(js)),
                cwd=app_root,
                profile="readonly",
                timeout=20,
                text=True,
            )).to_completed_process()
            if proc.returncode != 0:
                issues.append(f"JavaScript syntax failed in {js.relative_to(app_root)}: {(proc.stderr or proc.stdout).strip()[:180]}")
            else:
                checks.append(f"node --check {js.relative_to(app_root)}")
        else:
            warnings.append("node unavailable; skipped JavaScript syntax check")
            break

    expected = _expected_terms(request + "\n" + brief)
    visible = _visible_text(text) + "\n" + "\n".join(_read(path) for path in js_files[:8] if path.exists())
    missing_terms = [term for term in expected if term.lower() not in visible.lower()]
    if expected and len(missing_terms) > max(1, len(expected) // 2):
        issues.append("expected app terms missing from UI/content: " + ", ".join(missing_terms[:8]))
    if expected:
        checks.append("expected UI/content terms checked: " + ", ".join(expected[:8]))

    readme = _find_readme(app_root)
    if readme:
        checks.append(f"README found: {readme.relative_to(app_root)}")
    else:
        issues.append("missing README.md with run/open instructions")

    http_ok, http_issue, preview_path = _http_smoke(app_root)
    if http_ok:
        checks.append("local HTTP load returned 200")
    else:
        issues.append(http_issue)
    if preview_path:
        checks.append("browser preview screenshot captured")
    else:
        warnings.append("browser preview screenshot unavailable")

    summary = "Artisan app QA passed." if not issues else "Artisan app QA failed."
    return ArtisanAppQaResult(
        not issues,
        str(app_root),
        summary,
        issues,
        warnings,
        checks,
        preview_path,
        str(readme or ""),
    )


def _select_app_root(root: Path, changed_files: list[str]) -> Path | None:
    candidates: list[Path] = []
    for item in changed_files:
        path = root / item
        if path.name.lower() == "index.html":
            candidates.append(path.parent)
    candidates.extend(path.parent for path in root.rglob("index.html") if "node_modules" not in path.parts)
    if not candidates:
        return None
    candidates = sorted(set(candidates), key=lambda path: (len(path.parts), str(path)))
    return candidates[0]


def _linked_assets(html_text: str) -> list[str]:
    assets: list[str] = []
    for pattern in (
        r"<script[^>]+src=[\"']([^\"']+)[\"']",
        r"<link[^>]+href=[\"']([^\"']+)[\"']",
    ):
        assets.extend(match.group(1).split("#", 1)[0].split("?", 1)[0] for match in re.finditer(pattern, html_text, re.I))
    return [asset for asset in assets if asset]


def _is_external(asset: str) -> bool:
    return asset.startswith(("http://", "https://", "//", "data:"))


def _expected_terms(text: str) -> list[str]:
    snippets: list[str] = []
    for marker in ("track", "tracks", "include", "includes", "should let me", "should let users", "with"):
        for match in re.finditer(rf"\b{re.escape(marker)}\b([^.\n]+)", text, re.I):
            snippets.append(match.group(1))
    source = " ".join(snippets) or text
    stop = {
        "app", "web", "website", "frontend", "build", "create", "make", "real", "folder",
        "static", "html", "css", "javascript", "readme", "dependencies", "project", "named",
        "tiny", "simple", "small", "test", "artisan", "live", "files", "should", "users",
    }
    terms: list[str] = []
    for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", source):
        lowered = word.lower()
        if lowered in stop or lowered in terms:
            continue
        terms.append(lowered)
    return terms[:10]


def _visible_text(html_text: str) -> str:
    without_tags = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_text, flags=re.I | re.S)
    without_tags = re.sub(r"<[^>]+>", " ", without_tags)
    return html.unescape(re.sub(r"\s+", " ", without_tags))


def _http_smoke(app_root: Path) -> tuple[bool, str, str]:
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(*args, directory=str(app_root), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    preview_path = ""
    try:
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/"
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status != 200:
                return False, f"local HTTP load returned {response.status}", preview_path
            response.read(256)
        try:
            preview_path = _capture_browser_preview(app_root, url)
        except Exception:
            preview_path = ""
        return True, "", preview_path
    except Exception as exc:  # pragma: no cover - defensive reporting
        return False, f"local HTTP load failed: {exc}", preview_path
    finally:
        server.shutdown()
        server.server_close()


def _read(path: Path) -> str:
    try:
        return path.read_text("utf-8")
    except UnicodeDecodeError:
        return path.read_text("utf-8", errors="replace")
    except OSError:
        return ""


def _find_readme(app_root: Path) -> Path | None:
    for name in ("README.md", "readme.md"):
        path = app_root / name
        if path.exists() and path.is_file() and path.stat().st_size > 20:
            return path
    return None


def _css_quality_issue(path: Path) -> str:
    text = _read(path)
    if re.search(r"\b(?:font|box|border|text|grid|align|justify|margin|padding|line)\s+(?:family|sizing|radius|align|template|items|content|bottom|top|height)\s*:", text):
        return "contains malformed CSS property names with spaces"
    if "<style" in text.lower() or "</style>" in text.lower():
        return "CSS file contains HTML style tags"
    return ""


def _capture_browser_preview(app_root: Path, url: str) -> str:
    chrome = _chrome_binary()
    if not chrome:
        return ""
    qa_dir = app_root / ".maya_qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    screenshot = qa_dir / "app-preview.png"
    with tempfile.TemporaryDirectory(prefix="maya-app-chrome-") as tmp:
        proc = run_command(CommandSpec(
            argv=(
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--hide-scrollbars",
                "--window-size=1280,900",
                f"--user-data-dir={tmp}",
                f"--screenshot={screenshot}",
                url,
            ),
            cwd=app_root,
            text=True,
            timeout=8,
            profile="browser_headless",
            write_roots=(Path(tmp), qa_dir),
            network=True,
            sandbox=False,
        )).to_completed_process()
    if proc.returncode == 0 and screenshot.exists() and screenshot.stat().st_size > 1024:
        return str(screenshot)
    return ""


def _chrome_binary() -> str:
    for candidate in (
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ):
        if candidate and Path(candidate).exists():
            return str(candidate)
    return ""
