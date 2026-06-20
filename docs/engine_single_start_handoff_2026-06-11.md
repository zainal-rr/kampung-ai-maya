# Maya Engine Single-Start Handoff — 2026-06-11

## Scope

This handoff covers the follow-up to the intake guard patch:

> The Telegram poller lock prevents duplicate `getUpdates` loops, but the
> deeper runtime should also prevent a second Maya engine from starting.

The goal is not to remove the app controller. The app controller is expected to
run when `Kampung AI.app` is open in the Dock. The goal is to ensure that only
one `--engine` runtime can initialize channels, adapters, hotkeys, and Telegram.

## Live Evidence Before Patch

The current launchd job is correctly installed as the engine:

```text
launchctl print gui/$(id -u)/com.kampungai.maya

program = /Applications/Kampung AI.app/Contents/MacOS/Kampung AI
arguments = {
    /Applications/Kampung AI.app/Contents/MacOS/Kampung AI
    --engine
}
state = running
pid = 70022
```

The live plist also points to the app executable with `--engine`:

```text
~/Library/LaunchAgents/com.kampungai.maya.plist
ProgramArguments = [
  "/Applications/Kampung AI.app/Contents/MacOS/Kampung AI",
  "--engine"
]
```

`ps` showed two Kampung AI processes:

```text
/Applications/Kampung AI.app/Contents/MacOS/Kampung AI --engine
/Applications/Kampung AI.app/Contents/MacOS/Kampung AI
```

This is not automatically wrong:

- `--engine` is the launchd runtime that runs `main.py`.
- no-arg `Kampung AI` is the app controller that keeps the Dock app alive,
  installs/ensures launchd, and listens for app-controller hotkeys.

The risk was lower-level: `main.py` had no process-level engine lock. If another
engine was started manually, by an old app build, or by a restart overlap, it
could initialize all channels again. The Telegram poller lock would block
Telegram damage, but the rest of the runtime could still duplicate.

## Root Cause

Before this patch:

1. `kampung_ai_app.py` normal mode runs the controller.
2. `kampung_ai_app.py --engine` runs `main.py`.
3. `main.py` starts channel tasks directly:
   - health reporter
   - agent runtime
   - Telegram
   - hotkey voice
   - Omi/Mudra/camera adapters when enabled
4. There was no repo-wide engine lock before those tasks were created.

The Telegram-specific lock from the intake patch is still necessary, but it is
only a second line of defense. It cannot stop duplicate hotkeys, duplicate
hardware adapters, or duplicate background runtime tasks.

## Code Changes

### 1. New `maya_engine_lock.py`

New file:

```text
maya_engine_lock.py
```

It provides:

```python
acquire_engine_lock(lock_dir: Path | str | None = None) -> EngineLock | None
```

Behavior:

- Uses `fcntl.flock` on `logs/maya_engine.lock`.
- Writes the holder PID into the lock file.
- Returns `None` when another engine already holds the lock.
- Logs a CRITICAL message naming the lock path and holder PID.
- Releases automatically when the process dies.
- Can be disabled for deterministic tests with:

```text
MAYA_ENGINE_LOCK=0
```

### 2. `main.py` now acquires the engine lock before runtime initialization

Changed file:

```text
main.py
```

The lock is acquired immediately after logging setup and before:

- database initialization
- assistant construction
- health reporter
- Telegram channel
- hotkey voice channel
- hardware adapters
- agent runtime

If the lock is held, `main.py` returns without starting any channel task.

The lock is released in `finally` when the engine exits.

### 3. New deterministic smoke

New file:

```text
maya_engine_lock_smoke.py
```

It verifies:

1. first engine lock acquire succeeds
2. second acquire is refused
3. release allows reacquire
4. `MAYA_ENGINE_LOCK=0` disables the guard for tests

## Why This Fix Is Correct

This creates a layered startup safety model:

1. **App controller lock** in `kampung_ai_app.py`
   - allows only one Dock/controller process
   - controller may run alongside engine

2. **Engine lock** in `main.py`
   - allows only one full Maya runtime
   - protects all channels and adapters

3. **Telegram poller lock** in `telegram_channel.py`
   - allows only one Telegram `getUpdates` loop
   - protects intake even if future code accidentally bypasses the engine lock

This means a duplicate process can no longer silently initialize a second Maya
runtime.

## Important Deployment Note

The live engine that was already running before this patch does not yet hold the
new `maya_engine.lock`. The lock takes effect after restarting the launchd
engine.

Expected deploy command:

```bash
cd /Users/zainalabidinjamal/projects/kampung-ai
./venv/bin/python service_install.py restart
```

After restart, verify:

```bash
launchctl print gui/$(id -u)/com.kampungai.maya | grep -A5 arguments
ps aux | rg -i "Kampung AI|main.py" | rg -v rg
cat logs/maya_engine.lock
```

Expected:

- one `Kampung AI --engine` process
- optional one no-arg `Kampung AI` controller process if the Dock app is open
- `logs/maya_engine.lock` contains the engine PID

## Tests Run

Run after patch:

```bash
./venv/bin/python maya_engine_lock_smoke.py
./venv/bin/python telegram_intake_guard_smoke.py
./venv/bin/python service_install_smoke.py
./venv/bin/python kampung_ai_app_smoke.py
./venv/bin/python -m py_compile main.py maya_engine_lock.py telegram_poller_lock.py telegram_channel.py service_install.py kampung_ai_app.py
```

Expected output:

```text
maya_engine_lock_smoke: ok
telegram_intake_guard_smoke: ok
service_install_smoke: ok
kampung_ai_app_smoke: ok
py_compile: no output
```

Actual local run in this session:

```text
maya_engine_lock_smoke: ok
telegram_intake_guard_smoke: ok
service_install_smoke: ok
kampung_ai_app_smoke: ok
py_compile: ok
```

After one cleanup patch that moved `require_env()` under the lock `try/finally`,
the same test set was rerun and passed again.

## Live Deployment Performed In This Session

The launchd engine was restarted after the patch:

```bash
cd /Users/zainalabidinjamal/projects/kampung-ai
./venv/bin/python service_install.py restart
```

Live verification after restart:

```text
launchctl print gui/$(id -u)/com.kampungai.maya

state = running
program = /Applications/Kampung AI.app/Contents/MacOS/Kampung AI
arguments = {
    /Applications/Kampung AI.app/Contents/MacOS/Kampung AI
    --engine
}
pid = 68595
```

Process list after restart:

```text
/Applications/Kampung AI.app/Contents/MacOS/Kampung AI --engine
/Applications/Kampung AI.app/Contents/MacOS/Kampung AI
```

Interpretation:

- the `--engine` process is the actual Maya runtime
- the no-argument process is the Dock app/controller
- this is allowed; they have different roles

Engine lock file after restart:

```text
logs/maya_engine.lock -> 68595
```

Adversarial duplicate-engine test:

```bash
./venv/bin/python main.py
```

Result:

```text
CRITICAL [maya_engine_lock] Maya engine lock at
/Users/zainalabidinjamal/projects/kampung-ai/logs/maya_engine.lock
is held by pid 68595; refusing to start a duplicate engine.
```

Exit code was `0`, and no extra `main.py` or second engine process remained.

## What This Does Not Change

- Does not remove `com.kampungai.maya`.
- Does not remove `Kampung AI.app`.
- Does not change the launchd label.
- Does not change the app controller behavior.
- Does not rebuild `/Applications/Kampung AI.app`.
- Does not change Telegram allowlist behavior.
- Does not change document/Excel species logic.

## Remaining Follow-Up For Another Session

1. Verify after restart that `logs/maya_engine.lock` contains the active engine
   PID.
2. Decide whether launchd `KeepAlive` should stay unconditional or become a
   more specific crash-only policy. Current unconditional `KeepAlive` is okay
   for appliance behavior, but it will relaunch if the engine exits because a
   duplicate lock is held.
3. Inspect app build/deploy process later. This patch lives in repo `main.py`,
   so the engine picks it up after launchd restart, but changes to
   `kampung_ai_app.py` itself still require rebuilding `/Applications/Kampung AI.app`.
4. Keep the Telegram poller lock. Do not remove it just because the engine lock
   exists; it remains valuable defense-in-depth.
