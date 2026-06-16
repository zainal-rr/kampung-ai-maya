from __future__ import annotations

import subprocess


NETWORK_CHECKS = (
    ("Default route", ("route", "-n", "get", "default")),
    ("DNS config", ("scutil", "--dns")),
    ("Ping Cloudflare DNS", ("ping", "-c", "1", "1.1.1.1")),
    ("Ping google.com", ("ping", "-c", "1", "google.com")),
)


def run_network_diagnostics(timeout: int = 5) -> list[tuple[str, str, str]]:
    results = []
    for name, command in NETWORK_CHECKS:
        results.append((name, *_run(command, timeout)))
    return results


def summarize_network(results: list[tuple[str, str, str]]) -> str:
    failures = [name for name, status, _ in results if status != "ok"]
    if not failures:
        return "The basic checks passed: route, DNS, and two ping tests responded."
    joined = ", ".join(failures)
    return f"These checks need attention: {joined}."


def network_doc_sections(results: list[tuple[str, str, str]]) -> list[tuple[str, list[str]]]:
    sections = [("Summary", [summarize_network(results)])]
    sections.append(("Checks Run", [f"{name}: {status}" for name, status, _ in results]))
    failures = [f"{name}: {status}. {detail[:180]}" for name, status, detail in results if status != "ok"]
    sections.append((
        "Findings",
        failures or ["No failed basic route, DNS, or ping checks were observed in this diagnostic run."],
    ))
    sections.append((
        "Next Steps",
        [
            "Check whether Wi-Fi or Ethernet is connected.",
            "If DNS failed, try another resolver or restart the router.",
            "If IP ping works but domain ping fails, focus on DNS.",
            "If all pings fail, focus on router, ISP, or local link.",
        ],
    ))
    return sections


def _run(command: tuple[str, ...], timeout: int) -> tuple[str, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception as exc:
        return "error", str(exc)
    output = "\n".join(part for part in (result.stdout, result.stderr) if part.strip())
    status = "ok" if result.returncode == 0 else "needs attention"
    return status, output.strip()[:1200]
