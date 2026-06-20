from __future__ import annotations

from maya_core.reliability_incident_schema import (
    SUBSYSTEMS,
    IncidentOffender,
    OperationalIncident,
    derive_severity,
    effective_recovery_status,
)
from maya_core.reliability_incident_store import load_incidents


def recovery_split(incidents: list[OperationalIncident]) -> dict[str, int]:
    split = {"recovered": 0, "degraded": 0, "wedged": 0, "not_attempted": 0, "unknown": 0}
    for incident in incidents:
        split[effective_recovery_status(incident)] += 1
    return split


def top_offenders(incidents: list[OperationalIncident]) -> list[IncidentOffender]:
    groups: dict[tuple[str, str, str], list[OperationalIncident]] = {}
    for incident in incidents:
        groups.setdefault((incident.subsystem, incident.failure_class, incident.reason_code), []).append(incident)
    offenders: list[IncidentOffender] = []
    for (subsystem, failure_class, reason_code), rows in groups.items():
        severities = [derive_severity(row) for row in rows]
        split = recovery_split(rows)
        offenders.append(
            IncidentOffender(
                subsystem=subsystem,
                failure_class=failure_class,
                reason_code=reason_code,
                incident_count=len(rows),
                burst_count=sum(row.burst_count for row in rows),
                max_severity=max(severities) if severities else 0,
                impact_score=sum(severities),
                recovered=split["recovered"],
                degraded=split["degraded"],
                wedged=split["wedged"],
                open_count=sum(1 for row in rows if row.status == "open"),
            )
        )
    return sorted(offenders, key=lambda item: (item.impact_score, item.max_severity, item.incident_count), reverse=True)


def format_incident_report(incidents: list[OperationalIncident] | None = None) -> str:
    rows = load_incidents() if incidents is None else incidents
    lines = ["Operational incident ledger:"]
    if not rows:
        lines.append("No incidents observed. This means no incidents were recorded; detection coverage may still be incomplete.")
        return "\n".join(lines)
    lines.extend(_top_offender_lines(rows))
    lines.append(_recovery_split_line(rows))
    lines.extend(_open_incident_lines(rows))
    lines.extend(_serious_lines(rows))
    lines.extend(_coverage_lines(rows))
    return "\n".join(lines)


def _top_offender_lines(rows: list[OperationalIncident]) -> list[str]:
    lines = ["Top offenders by impact:"]
    for index, offender in enumerate(top_offenders(rows)[:10], start=1):
        lines.append(
            f"{index}) {offender.subsystem}/{offender.reason_code}: "
            f"impact={offender.impact_score} incidents={offender.incident_count} bursts={offender.burst_count} "
            f"severity={offender.max_severity} recovered/degraded/wedged="
            f"{offender.recovered}/{offender.degraded}/{offender.wedged}"
        )
    return lines


def _recovery_split_line(rows: list[OperationalIncident]) -> str:
    split = recovery_split(rows)
    return (
        "Recovery split: "
        f"recovered={split['recovered']} degraded={split['degraded']} wedged={split['wedged']} "
        f"not_attempted={split['not_attempted']} unknown={split['unknown']}"
    )


def _open_incident_lines(rows: list[OperationalIncident]) -> list[str]:
    lines = ["Open/unresolved incidents:"]
    open_rows = [row for row in rows if row.status == "open"]
    if not open_rows:
        return lines + ["- none"]
    return lines + [
        f"- {row.subsystem}/{row.reason_code}: operation={row.operation} last_seen={row.last_seen}"
        for row in open_rows[:10]
    ]


def _serious_lines(rows: list[OperationalIncident]) -> list[str]:
    lines = ["Serious but rare (severity 4-5):"]
    serious = [row for row in rows if derive_severity(row) >= 4]
    if not serious:
        return lines + ["- none"]
    return lines + [
        f"- severity={derive_severity(row)} {row.subsystem}/{row.reason_code}: "
        f"operation={row.operation} status={row.status} recovery={effective_recovery_status(row)}"
        for row in serious[:10]
    ]


def _coverage_lines(rows: list[OperationalIncident]) -> list[str]:
    observed = {row.subsystem for row in rows}
    lines = ["Subsystem coverage:"]
    for subsystem in SUBSYSTEMS:
        if subsystem in observed:
            lines.append(f"- {subsystem}: incidents observed")
        else:
            lines.append(f"- {subsystem}: no incidents observed")
    return lines
