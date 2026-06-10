"""Deterministic smoke for domain knowledge retrieval (skill-file-driven RAG).

Covers the contract:
1. The proposed network skill parses: triggers, vetoes, KB root, retrieval order.
2. Real config prompts retrieve the right recipe chunks (with rollback intact).
3. Non-domain prompts and vetoed prompts inject nothing (silence over noise).
4. The character budget holds.
5. Proposed skills stay inert: the default active/ scan ignores them.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from domain_knowledge import (
    DEFAULT_SKILL_DIR,
    detect_domain_skill,
    domain_knowledge_context,
    load_domain_skills,
)

PROPOSED_SKILL = Path("maya_skills") / "proposed" / "network_engineering.md"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _parsing_checks() -> None:
    skills = load_domain_skills(PROPOSED_SKILL.parent)
    by_id = {skill.skill_id: skill for skill in skills}
    _require("network_engineering" in by_id and "finance_credit_analysis" in by_id,
             f"expected network + finance domain skills, got {sorted(by_id)}")
    skill = by_id["network_engineering"]
    _require(skill.kb_root == "docs/networking", f"wrong KB root: {skill.kb_root}")
    _require(any("recipes" in p for p in skill.retrieval_order), f"retrieval order missing recipes: {skill.retrieval_order}")
    _require("vrf" in skill.strong_triggers and "ospf" in skill.strong_triggers, f"acronym triggers missing: {skill.strong_triggers[:10]}")
    _require("how do i configure" in skill.strong_triggers, "quoted phrase trigger missing")
    _require("router" in skill.weak_triggers, "weak trigger 'router' missing")
    _require("router" not in skill.non_triggers, "veto list must not contain single trigger words")
    _require(any("home wi-fi" in v for v in skill.non_triggers), f"phrase veto missing: {skill.non_triggers}")
    finance = by_id["finance_credit_analysis"]
    _require(finance.kb_root == "docs/finance", f"wrong finance KB root: {finance.kb_root}")
    _require("liquidity gap" in finance.strong_triggers and "loan book" in finance.strong_triggers,
             f"finance quoted triggers missing: {finance.strong_triggers[:8]}")
    _require("roa" in finance.strong_triggers, "finance acronym trigger ROA missing")


def _activation_checks() -> None:
    skills = load_domain_skills(PROPOSED_SKILL.parent)
    cases_active = (
        "create a vrf for customer A on the PE router",
        "how do I configure HSRP on the campus distribution boundary",
        "why is routing broken between the leaf switches",
        "design the network for a new branch campus",
    )
    for prompt in cases_active:
        _require(detect_domain_skill(prompt, skills) is not None, f"should activate: {prompt!r}")
    cases_silent = (
        "make me a budget tracker for the Seoul trip",
        "remind me to call the dentist tomorrow",
        "my home wi-fi keeps dropping on the couch",  # vetoed consumer case
        "explain the history of the roman empire",
    )
    for prompt in cases_silent:
        _require(detect_domain_skill(prompt, skills) is None, f"should stay silent: {prompt!r}")


def _retrieval_checks() -> None:
    context, skill = domain_knowledge_context(
        "create a vrf for customer A with rd and route targets",
        skill_dir=PROPOSED_SKILL.parent,
    )
    _require(skill is not None, "vrf prompt should match the network skill")
    _require("vrf" in context.lower(), "vrf prompt should retrieve VRF content")
    _require("[source: docs/networking/" in context, "context must cite its source path")
    _require("rollback" in context.lower(), "recipe chunks should surface the rollback contract")
    _require("unverified general knowledge" in context, "honesty fallback instruction missing")

    hsrp_context, _ = domain_knowledge_context(
        "how do I configure HSRP at the campus layer 3 boundary",
        skill_dir=PROPOSED_SKILL.parent,
    )
    _require("hsrp" in hsrp_context.lower(), "hsrp prompt should retrieve HSRP content")
    _require(hsrp_context != context, "different prompts should retrieve different chunks")

    silent_context, silent_skill = domain_knowledge_context(
        "make me a budget tracker for groceries",
        skill_dir=PROPOSED_SKILL.parent,
    )
    _require(silent_context == "" and silent_skill is None, "non-domain prompt must inject nothing")

    tight_context, _ = domain_knowledge_context(
        "create a vrf for customer A with rd and route targets",
        skill_dir=PROPOSED_SKILL.parent,
        budget_chars=1200,
    )
    _require(len(tight_context) <= 1200 + 200, f"budget not respected: {len(tight_context)} chars")


def _finance_checks() -> None:
    skills = load_domain_skills(PROPOSED_SKILL.parent)
    case = (
        "A non-deposit financial institution reports a loan book of 200 million and a stable ROA of 7%, "
        "with 60% of exposures restructured and extended. Quantify the liquidity gap and evaluate the "
        "institution's ability to meet near-term obligations. Assess the feasibility of the proposed "
        "Preference Share issuance."
    )
    matched = detect_domain_skill(case, skills)
    _require(matched is not None and matched.skill_id == "finance_credit_analysis",
             f"banking case should match finance skill, got {matched.skill_id if matched else None}")
    context, skill = domain_knowledge_context(case, skill_dir=PROPOSED_SKILL.parent)
    _require(skill is not None and skill.skill_id == "finance_credit_analysis", "finance retrieval should fire")
    _require("[source: docs/finance/recipes/" in context, "case should retrieve a finance recipe with citation")
    _require("limitations" in context.lower(), "finance recipes must retrieve whole (with limitations)")
    # A focused liquidity question must pull the liquidity recipe specifically.
    gap_context, _ = domain_knowledge_context(
        "quantify the liquidity gap given obligations of 60 million and expected inflows of 30 million",
        skill_dir=PROPOSED_SKILL.parent,
    )
    _require("coverage ratio" in gap_context.lower(), "liquidity recipe method should be present")
    _require("liquidity_gap_analysis" in gap_context, "liquidity prompt should cite the liquidity recipe")
    silent, none_skill = domain_knowledge_context(
        "set up a household budget for the family groceries", skill_dir=PROPOSED_SKILL.parent
    )
    _require(silent == "" and none_skill is None, "household budget must not trigger the finance pack")

    from skill_evaluator import evaluate_skill_scaffold

    results = evaluate_skill_scaffold("maya_skills/proposed/finance_credit_analysis.md")
    failed = [name for name, (status, _) in results.items() if status != "passed"]
    _require(not failed, f"finance skill failed scaffold checks: {failed}")


def _inert_until_active_checks() -> None:
    # The default scan only reads maya_skills/active. The network skill lives
    # in proposed/, so default retrieval must not use it...
    skills = load_domain_skills(DEFAULT_SKILL_DIR)
    _require(
        all(skill.skill_id != "network_engineering" for skill in skills),
        "proposed skill must stay inert until promoted to active/",
    )
    # ...and promoting it (simulated in a temp dir) turns retrieval on.
    with tempfile.TemporaryDirectory(prefix="maya-domain-active-") as tmp:
        active = Path(tmp)
        shutil.copy2(PROPOSED_SKILL, active / "network_engineering.md")
        context, skill = domain_knowledge_context(
            "create a vrf for customer A",
            skill_dir=active,
        )
        _require(skill is not None and "vrf" in context.lower(), "promoted skill should retrieve")


def main() -> None:
    _parsing_checks()
    _activation_checks()
    _retrieval_checks()
    _finance_checks()
    _inert_until_active_checks()
    print("skill_domain_smoke: ok")


if __name__ == "__main__":
    main()
