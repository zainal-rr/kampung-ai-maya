import subprocess


BROWSER_APPS = {"Google Chrome", "Safari"}

class OSBridge:
    """
    OS Control Bridge for Kampung AI.
    Controls iMac system functions using AppleScript via subprocess.
    """

    def _run_applescript(self, script: str) -> str:
        """Helper to execute AppleScript and return output."""
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            # Re-raise with a cleaner message or handle specific errors
            raise RuntimeError(f"AppleScript error: {e.stderr.strip()}") from e

    def set_volume(self, level: int):
        """Sets system volume (0-100)."""
        if not (0 <= level <= 100):
            raise ValueError("Volume level must be between 0 and 100.")
        self._run_applescript(f"set volume output volume {level}")

    def get_volume(self) -> int:
        return int(self._run_applescript("output volume of (get volume settings)") or 0)

    def change_volume(self, delta: int) -> int:
        level = max(0, min(100, self.get_volume() + delta))
        self.set_volume(level)
        return level

    def mute(self):
        self._run_applescript("set volume with output muted")

    def unmute(self):
        self._run_applescript("set volume without output muted")

    def toggle_fullscreen(self):
        """Toggles full screen for the active window using Cmd+Ctrl+F."""
        script = 'tell application "System Events" to keystroke "f" using {command down, control down}'
        self._run_applescript(script)

    def switch_app(self, name: str):
        """Launches the app, brings it forward, and opens a window when needed."""
        try:
            self._launch_app(name)
            self._activate_app(name)
            self._ensure_window(name)
            self._verify_frontmost(name)
        except RuntimeError as e:
            # Specific handling for invalid app names
            if "invalid" in str(e).lower() or "not found" in str(e).lower():
                raise ValueError(f"Application '{name}' not found or could not be activated.") from e
            raise

    def _launch_app(self, name: str):
        try:
            subprocess.run(
                ["open", "-a", name],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or "").strip()
            raise RuntimeError(f"Application '{name}' not found or could not be opened. {detail}") from e

    def _activate_app(self, name: str):
        safe_name = name.replace('"', '\\"')
        self._run_applescript(f'tell application "{safe_name}" to activate')

    def _ensure_window(self, name: str):
        if name not in BROWSER_APPS:
            return
        safe_name = name.replace('"', '\\"')
        script = (
            f'tell application "{safe_name}"\n'
            "activate\n"
            "if (count of windows) is 0 then make new window\n"
            "set index of window 1 to 1\n"
            "end tell"
        )
        self._run_applescript(script)
        try:
            self._raise_window(name)
        except RuntimeError:
            pass

    def _raise_window(self, name: str):
        safe_name = name.replace('"', '\\"')
        script = (
            'tell application "System Events"\n'
            f'tell process "{safe_name}"\n'
            "set frontmost to true\n"
            "if exists window 1 then\n"
            'set value of attribute "AXMinimized" of window 1 to false\n'
            'perform action "AXRaise" of window 1\n'
            "end if\n"
            "end tell\n"
            "end tell"
        )
        self._run_applescript(script)

    def _verify_frontmost(self, name: str):
        frontmost = self.get_frontmost_app()
        if frontmost != name:
            raise RuntimeError(f"Opened {name}, but {frontmost} is still frontmost.")

    def open_url(self, url: str, app_name: str = "Google Chrome"):
        """Opens a URL in the preferred browser and brings it forward."""
        safe_url = url.replace("\\", "\\\\").replace('"', "%22")
        script = (
            f'tell application "{app_name}" to activate\n'
            f'open location "{safe_url}"'
        )
        self._run_applescript(script)
        self._ensure_window(app_name)
        self._verify_frontmost(app_name)

    def open_file(self, path: str, app_name: str | None = None):
        """Opens a local file, optionally with a specific app."""
        command = ["open", path] if not app_name else ["open", "-a", app_name, path]
        try:
            subprocess.run(command, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or "").strip()
            raise RuntimeError(f"Could not open {path}. {detail}") from e
        if app_name:
            self._verify_frontmost(app_name)

    def press_shortcut(self, shortcut: str):
        """Presses a keyboard shortcut in the frontmost app."""
        key, modifiers = _parse_shortcut(shortcut)
        if key in SPECIAL_KEYS:
            script = f'tell application "System Events" to key code {SPECIAL_KEYS[key]}{_modifier_clause(modifiers)}'
        else:
            safe_key = key.replace('"', '\\"')
            script = f'tell application "System Events" to keystroke "{safe_key}"{_modifier_clause(modifiers)}'
        self._run_applescript(script)

    def type_text(self, text: str):
        """Types text into the frontmost app."""
        safe_text = text.replace("\\", "\\\\").replace('"', '\\"')
        self._run_applescript(f'tell application "System Events" to keystroke "{safe_text}"')

    def get_frontmost_app(self) -> str:
        """Returns the name of the application currently in focus."""
        script = 'tell application "System Events" to get name of first process whose frontmost is true'
        return self._run_applescript(script)

    def list_running_apps(self) -> list[str]:
        script = 'tell application "System Events" to get name of (every process whose background only is false)'
        apps = self._run_applescript(script)
        return [item.strip() for item in apps.split(",") if item.strip()]

    def notify(self, title: str, message: str):
        """Displays a macOS system notification."""
        # Escaping double quotes in message and title for AppleScript
        safe_title = title.replace('"', '\\"')
        safe_message = message.replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        self._run_applescript(script)


SPECIAL_KEYS = {
    "return": 36,
    "enter": 36,
    "tab": 48,
    "escape": 53,
    "esc": 53,
    "space": 49,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "delete": 51,
    "backspace": 51,
}


def _parse_shortcut(shortcut: str) -> tuple[str, list[str]]:
    parts = [part.strip().lower() for part in shortcut.replace("+", " ").split() if part.strip()]
    modifiers = []
    key = ""
    for part in parts:
        if part in {"cmd", "command"}:
            modifiers.append("command down")
        elif part in {"ctrl", "control"}:
            modifiers.append("control down")
        elif part in {"opt", "option", "alt"}:
            modifiers.append("option down")
        elif part == "shift":
            modifiers.append("shift down")
        else:
            key = part
    if not key:
        raise ValueError("Shortcut needs a key.")
    return key, modifiers


def _modifier_clause(modifiers: list[str]) -> str:
    return f" using {{{', '.join(modifiers)}}}" if modifiers else ""

if __name__ == "__main__":
    # Simple test suite
    bridge = OSBridge()
    try:
        current_app = bridge.get_frontmost_app()
        print(f"Current app: {current_app}")
        bridge.notify("Kampung AI", f"OSBridge initialized. Frontmost app: {current_app}")
    except Exception as e:
        print(f"Initialization test failed: {e}")
