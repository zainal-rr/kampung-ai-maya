from __future__ import annotations

from hardening_audit import (
    capability_readiness_report,
    demo_evidence_items,
    hardening_audit_summary,
    public_report_redaction_issues,
    public_redaction_paths,
    rollback_drill_items,
    route_cost_audit,
)


def main() -> None:
    route_items = route_cost_audit()
    _require(route_items and all(item.passed for item in route_items), "route/model audit failed")
    _require("telegram: ready | 90%" in capability_readiness_report(), "capability report missing telegram")
    _require(all(item.passed for item in rollback_drill_items()), "rollback drill guardrails missing")
    _require(all(item.passed for item in demo_evidence_items()), "latest demo evidence failed")
    _require(not public_report_redaction_issues(public_redaction_paths()), "public report redaction failed")
    summary = hardening_audit_summary()
    _require("demo evidence" in summary and "privacy/redaction issues" in summary, "audit summary incomplete")
    print("hardening_audit_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
