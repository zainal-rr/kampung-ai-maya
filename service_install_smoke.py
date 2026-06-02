from __future__ import annotations

import service_install


def main() -> None:
    calls = []
    old_run = service_install.subprocess.run

    def fake_run(args, **kwargs):
        calls.append(tuple(args))
        class Result:
            returncode = 0
            stderr = ""
        return Result()

    try:
        service_install.subprocess.run = fake_run
        service_install.restart()
        service_install.restart_weekly_memory()
    finally:
        service_install.subprocess.run = old_run
    assert any(call[:2] == ("launchctl", "bootout") for call in calls)
    assert any(call[:2] == ("launchctl", "bootstrap") for call in calls)
    assert any(call[:2] == ("launchctl", "enable") for call in calls)
    weekly = service_install.build_weekly_memory_plist()
    assert weekly["StartCalendarInterval"] == {"Weekday": 0, "Hour": 20, "Minute": 0}
    assert any(str(item).endswith("weekly_memory.py") for item in weekly["ProgramArguments"])
    print("service_install_smoke: ok")


if __name__ == "__main__":
    main()
