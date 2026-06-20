from __future__ import annotations

import plistlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
APP_NAME = "Kampung AI"
BUNDLE_ID = "ai.kampung.KampungAI"
SOURCE_ICON = ROOT / "assets" / "brand" / "kampung-ai-living-bamboo-upscaled-4096.png"
SOURCE_ICON_TILE_CROP = (485, 525, 3605, 3645)
SOURCE_ICON_TILE_RADIUS_RATIO = 0.150
ICON_CANVAS_SIZE = 1024
ICON_TILE_SCALE = 0.860
ICON_FILE_STEM = "KampungAI"
APP_DESTINATION = Path("/Applications") / f"{APP_NAME}.app"
ENTRYPOINT = ROOT / "kampung_ai_app.py"


def main() -> None:
    _require_pyinstaller()
    with tempfile.TemporaryDirectory(prefix="kampung-ai-app-build-") as tmp:
        build_root = Path(tmp)
        icon_path = _build_icon(build_root)
        built_app = _run_pyinstaller(build_root, icon_path)
        _install_asset_catalog(build_root, built_app, build_root / "KampungAI-icon-source.png")
        _patch_info_plist(built_app)
        _install_app(built_app)
    _codesign(APP_DESTINATION)
    print(f"Built and installed {APP_DESTINATION}")


def _require_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit("PyInstaller is missing. Install it with ./venv/bin/python -m pip install pyinstaller") from exc


def _build_icon(build_root: Path) -> Path:
    if not SOURCE_ICON.exists():
        raise FileNotFoundError(SOURCE_ICON)
    icon_source = _prepare_icon_source(build_root)
    iconset = build_root / "KampungAI.iconset"
    iconset.mkdir(parents=True)
    for size in (16, 32, 128, 256, 512):
        _resize_icon(icon_source, size, iconset / f"icon_{size}x{size}.png")
        _resize_icon(icon_source, size * 2, iconset / f"icon_{size}x{size}@2x.png")
    icns = build_root / f"{ICON_FILE_STEM}.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)
    return icns


def _install_asset_catalog(build_root: Path, app_path: Path, icon_source: Path) -> None:
    xcassets = build_root / "KampungAI.xcassets"
    appiconset = xcassets / "AppIcon.appiconset"
    appiconset.mkdir(parents=True)

    images = []
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            pixel_size = size * scale
            filename = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
            _resize_icon(icon_source, pixel_size, appiconset / filename)
            images.append(
                {
                    "idiom": "mac",
                    "size": f"{size}x{size}",
                    "scale": f"{scale}x",
                    "filename": filename,
                }
            )
    (appiconset / "Contents.json").write_text(
        json.dumps({"images": images, "info": {"version": 1, "author": "xcode"}}, indent=2),
        encoding="utf-8",
    )

    partial_info = build_root / "assetcatalog-info.plist"
    subprocess.run(
        [
            "xcrun",
            "actool",
            str(xcassets),
            "--compile",
            str(app_path / "Contents" / "Resources"),
            "--platform",
            "macosx",
            "--minimum-deployment-target",
            "15.0",
            "--app-icon",
            "AppIcon",
            "--output-partial-info-plist",
            str(partial_info),
        ],
        check=True,
    )


def _prepare_icon_source(build_root: Path) -> Path:
    output = build_root / "KampungAI-icon-source.png"
    # The source artwork includes a large outer canvas; the app icon should use
    # the inner rounded-square Kampung AI mark with transparent outside padding.
    # The padding keeps the Dock icon optically aligned with normal macOS icons.
    with Image.open(SOURCE_ICON) as image:
        tile = image.crop(SOURCE_ICON_TILE_CROP).convert("RGBA")
        radius = round(min(tile.size) * SOURCE_ICON_TILE_RADIUS_RATIO)
        mask = Image.new("L", tile.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, tile.width - 1, tile.height - 1), radius=radius, fill=255)
        tile.putalpha(mask)
        tile_size = round(ICON_CANVAS_SIZE * ICON_TILE_SCALE)
        tile = tile.resize((tile_size, tile_size), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (ICON_CANVAS_SIZE, ICON_CANVAS_SIZE), (255, 255, 255, 0))
        offset = ((ICON_CANVAS_SIZE - tile_size) // 2, (ICON_CANVAS_SIZE - tile_size) // 2)
        canvas.alpha_composite(tile, offset)
        canvas.save(output)
    return output


def _resize_icon(source: Path, size: int, output: Path) -> None:
    subprocess.run(
        ["sips", "-z", str(size), str(size), str(source), "--out", str(output)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run_pyinstaller(build_root: Path, icon_path: Path) -> Path:
    dist_path = build_root / "dist"
    work_path = build_root / "work"
    spec_path = build_root / "spec"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(icon_path),
        "--hidden-import",
        "ctypes.util",
        "--osx-bundle-identifier",
        BUNDLE_ID,
        "--distpath",
        str(dist_path),
        "--workpath",
        str(work_path),
        "--specpath",
        str(spec_path),
        str(ENTRYPOINT),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    built_app = dist_path / f"{APP_NAME}.app"
    if not built_app.exists():
        raise FileNotFoundError(built_app)
    return built_app


def _patch_info_plist(app_path: Path) -> None:
    plist_path = app_path / "Contents" / "Info.plist"
    with plist_path.open("rb") as file_obj:
        data = plistlib.load(file_obj)
    data.update(
        {
            "CFBundleDisplayName": APP_NAME,
            "CFBundleName": APP_NAME,
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleIconFile": f"{ICON_FILE_STEM}.icns",
            "CFBundleIconName": "AppIcon",
            "CFBundleShortVersionString": "0.1.2",
            "CFBundleVersion": "3",
            "NSMicrophoneUsageDescription": "Kampung AI uses the microphone only after Zainal opens the Maya voice session.",
            "NSCameraUsageDescription": "Kampung AI uses the approved external camera only when Maya Eye is explicitly enabled.",
            "NSAppleEventsUsageDescription": "Kampung AI controls local apps only when Zainal asks Maya to act on the iMac.",
            "NSInputMonitoringUsageDescription": "Kampung AI listens for the configured local hotkeys that open and close Maya voice.",
            "NSScreenCaptureUsageDescription": "Kampung AI captures the screen only for explicit Maya screen-sight requests.",
            "NSHighResolutionCapable": True,
        }
    )
    with plist_path.open("wb") as file_obj:
        plistlib.dump(data, file_obj)


def _install_app(built_app: Path) -> None:
    if APP_DESTINATION.exists():
        shutil.rmtree(APP_DESTINATION)
    shutil.copytree(built_app, APP_DESTINATION, symlinks=True)


def _codesign(app_path: Path) -> None:
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app_path)], check=True)


if __name__ == "__main__":
    main()
