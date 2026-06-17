from __future__ import annotations

import fcntl
import os
import runpy
import signal
import sys
import threading
import time
from pathlib import Path


APP_NAME = "Kampung AI"
DEFAULT_REPO_ROOT = Path("/Users/zainalabidinjamal/projects/kampung-ai")


def main() -> None:
    repo_root = _prepare_runtime_paths()
    if "--engine" in sys.argv:
        _run_engine(repo_root)
    else:
        _run_controller(repo_root)


def _prepare_runtime_paths() -> Path:
    repo_root = Path(os.getenv("KAMPUNG_AI_REPO_ROOT", DEFAULT_REPO_ROOT)).expanduser().resolve()
    if not repo_root.exists():
        raise FileNotFoundError(f"Kampung AI repo root not found: {repo_root}")
    os.environ["KAMPUNG_AI_REPO_ROOT"] = str(repo_root)
    os.environ.setdefault("KAMPUNG_AI_APP_PATH", str(_current_app_path()))
    os.chdir(repo_root)
    _prepend_path(repo_root)
    for path in _venv_stdlib_paths(repo_root):
        _prepend_path(path)
    site_packages = _venv_site_packages(repo_root)
    if site_packages:
        _prepend_path(site_packages)
    return repo_root


def _run_engine(repo_root: Path) -> None:
    runpy.run_path(str(repo_root / "main.py"), run_name="__main__")


def _load_service_install_module():
    from maya_core import service_install

    return service_install


def _run_controller(repo_root: Path) -> None:
    controller_lock = _acquire_controller_lock()
    if controller_lock is None:
        _controller_log(repo_root, f"{APP_NAME} controller is already running.")
        return

    service_install = _load_service_install_module()
    if hasattr(service_install, "ensure_running"):
        service_install.ensure_running()
    else:
        service_install.install()

    if _run_macos_app_loop(service_install, repo_root):
        return

    stop_event = threading.Event()

    def request_stop(signum, _frame) -> None:
        _controller_log(repo_root, f"{APP_NAME} received signal {signum}; stopping Maya.")
        stop_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, request_stop)

    _controller_log(repo_root, f"{APP_NAME} is running. Quit the app to stop Maya.")
    try:
        while not stop_event.wait(1.0):
            pass
    finally:
        _controller_shutdown(service_install, repo_root)


def _acquire_controller_lock():
    lock_dir = Path.home() / "Library" / "Application Support" / APP_NAME
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = (lock_dir / "controller.lock").open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def _run_macos_app_loop(service_install, repo_root: Path) -> bool:
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyRegular
        from Foundation import NSObject
    except Exception:
        return False

    hotkey_listener = _start_controller_hotkeys(repo_root)

    class KampungAIAppDelegate(NSObject):
        def applicationShouldTerminateAfterLastWindowClosed_(self, _application):
            return False

        def applicationWillTerminate_(self, _notification):
            if hotkey_listener is not None:
                hotkey_listener.stop()
            _controller_shutdown(service_install, repo_root)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = KampungAIAppDelegate.alloc().init()
    app.setDelegate_(delegate)

    def request_stop(signum, _frame) -> None:
        _controller_log(repo_root, f"{APP_NAME} received signal {signum}; stopping Maya.")
        app.terminate_(None)

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, request_stop)

    _controller_log(repo_root, f"{APP_NAME} is running. Quit the app to stop Maya.")
    app.run()
    return True


def _start_controller_hotkeys(repo_root: Path):
    try:
        from maya_core.mac_hotkey import CarbonHotKeyListener
    except Exception as exc:
        _controller_log(repo_root, f"{APP_NAME} could not load Carbon hotkeys: {exc}")
        return None

    start_hotkey = os.getenv("MAYA_VOICE_HOTKEY", "<alt>+<space>")
    stop_hotkey = os.getenv("MAYA_VOICE_STOP_HOTKEY", "<alt>+<esc>")

    def toggle_voice() -> None:
        _touch_voice_trigger(repo_root / os.getenv("MAYA_VOICE_TOGGLE_TRIGGER_FILE", ".maya_voice_toggle"))
        _controller_log(repo_root, f"{APP_NAME} hotkey: toggle voice")

    def stop_voice() -> None:
        _touch_voice_trigger(repo_root / os.getenv("MAYA_VOICE_STOP_TRIGGER_FILE", ".maya_voice_stop"))
        _controller_log(repo_root, f"{APP_NAME} hotkey: stop voice")

    listener = CarbonHotKeyListener({
        start_hotkey: toggle_voice,
        stop_hotkey: stop_voice,
    })
    listener.start()
    _controller_log(repo_root, f"{APP_NAME} controller hotkeys live: start {start_hotkey}, stop {stop_hotkey}")
    return listener


def _controller_shutdown(service_install, repo_root: Path) -> None:
    _touch_voice_trigger(repo_root / os.getenv("MAYA_VOICE_STOP_TRIGGER_FILE", ".maya_voice_stop"))
    if os.getenv("KAMPUNG_AI_CONTROLLER_UNLOADS_SERVICE", "0") == "1":
        _controller_log(repo_root, f"{APP_NAME} is quitting; unloading Maya.")
        service_install.uninstall()
        return
    _controller_log(repo_root, f"{APP_NAME} is quitting; requested voice stop; engine service remains installed.")


def _touch_voice_trigger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{time.time_ns()}\n", encoding="utf-8")


def _controller_log(repo_root: Path, message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
    print(message, flush=True)
    try:
        logs = repo_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "kampung_ai_controller.log").open("a", encoding="utf-8") as file_obj:
            file_obj.write(line)
    except Exception:
        pass


def _current_app_path() -> Path:
    executable = Path(sys.executable).resolve()
    if executable.parent.name == "MacOS" and executable.parent.parent.name == "Contents":
        return executable.parent.parent.parent
    return Path("/Applications") / f"{APP_NAME}.app"


def _venv_site_packages(repo_root: Path) -> Path | None:
    lib_dir = repo_root / "venv" / "lib"
    if not lib_dir.exists():
        return None
    candidates = sorted(lib_dir.glob("python*/site-packages"), reverse=True)
    return candidates[0] if candidates else None


def _venv_stdlib_paths(repo_root: Path) -> list[Path]:
    site_packages = _venv_site_packages(repo_root)
    if site_packages is None:
        return []

    version_dir = site_packages.parent.name
    venv_cfg = repo_root / "venv" / "pyvenv.cfg"
    if not venv_cfg.exists():
        return []

    home = None
    for line in venv_cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "home":
            home = Path(value.strip()).expanduser()
            break

    if home is None:
        return []

    python_root = home.parent if home.name == "bin" else home
    version = version_dir.removeprefix("python")
    candidates = [
        python_root / "lib" / version_dir,
        python_root / "Frameworks" / "Python.framework" / "Versions" / version / "lib" / version_dir,
    ]

    paths: list[Path] = []
    for candidate in candidates:
        if candidate.exists():
            paths.append(candidate)
            dynload = candidate / "lib-dynload"
            if dynload.exists():
                paths.append(dynload)
    return paths


def _prepend_path(path: Path) -> None:
    raw = str(path)
    if raw not in sys.path:
        sys.path.insert(0, raw)


if __name__ == "__main__":
    main()
