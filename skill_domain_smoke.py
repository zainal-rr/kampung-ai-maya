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
    domain_knowledge_context_for_skill,
    load_domain_skills,
)

PROPOSED_SKILL = Path("maya_skills") / "proposed" / "network_engineering.md"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _parsing_checks() -> None:
    skills = load_domain_skills(PROPOSED_SKILL.parent)
    by_id = {skill.skill_id: skill for skill in skills}
    _require(
        "network_engineering" in by_id
        and "finance_credit_analysis" in by_id
        and "cloud_solution_architecture" in by_id,
        f"expected network + finance + cloud domain skills, got {sorted(by_id)}",
    )
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
    cloud = by_id["cloud_solution_architecture"]
    _require(cloud.kb_root == "docs/cloud", f"wrong cloud KB root: {cloud.kb_root}")
    _require("aws" in cloud.strong_triggers and "azure" in cloud.strong_triggers,
             f"cloud provider triggers missing: {cloud.strong_triggers[:10]}")
    _require("landing zone" in cloud.strong_triggers and "rto" in cloud.strong_triggers,
             "cloud quoted/acronym triggers missing")
    _require("network" not in cloud.weak_triggers,
             "cloud pack must not claim the bare word 'network' (collision with network_engineering)")
    _require(any("icloud" in v for v in cloud.non_triggers), f"cloud veto missing: {cloud.non_triggers}")


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
    grocery_silent, _ = domain_knowledge_context(
        "help me plan this month's grocery budget", skill_dir=PROPOSED_SKILL.parent
    )
    _require(grocery_silent == "", "personal grocery budget must stay vetoed (budget Excel lane)")

    # Phase 5 live finding 2026-06-12: singular follow-up wording missed the
    # plural trigger. Singular variant + the investor follow-up must now match.
    finance_skill = next(s for s in skills if s.skill_id == "finance_credit_analysis")
    _require("preference share" in finance_skill.strong_triggers,
             "singular 'preference share' trigger missing")
    followup = "now assess the preference share issuance from an investor's perspective"
    followup_ctx, followup_skill = domain_knowledge_context(followup, skill_dir=PROPOSED_SKILL.parent)
    _require(followup_skill is not None and followup_skill.skill_id == "finance_credit_analysis",
             "investor follow-up should now match finance directly")
    _require("preference_share_feasibility" in followup_ctx,
             "investor follow-up should retrieve the feasibility recipe")
    # Sticky path (trigger-free follow-up against a KNOWN skill) must retrieve
    # by token overlap and fail silent on unrelated follow-ups.
    sticky_ctx = domain_knowledge_context_for_skill(
        "now quantify the gap again with obligations of 60 million and inflows of 30 million",
        "finance_credit_analysis",
        skill_dir=PROPOSED_SKILL.parent,
    )
    _require("liquidity_gap_analysis" in sticky_ctx, "sticky retrieval should pull the liquidity recipe")
    _require("Domain answer contract" in sticky_ctx, "answer contract missing from sticky context")
    unrelated_sticky = domain_knowledge_context_for_skill(
        "remind me to call the dentist tomorrow",
        "finance_credit_analysis",
        skill_dir=PROPOSED_SKILL.parent,
    )
    _require(unrelated_sticky == "", "unrelated follow-up must inject nothing via sticky path")
    # The answer contract (Phase 5 partial fixes) must ride every context.
    _require("Domain answer contract" in followup_ctx, "answer contract missing from context")
    _require("compute and state the range" in followup_ctx, "range rule missing from contract")

    # Breadth: each new discipline must route to the finance pack and pull its recipe.
    breadth = {
        "valuation/dcf_valuation": "build a discounted cash flow valuation with WACC and terminal value",
        "valuation/comparable_companies": "value the target using comparable companies EV/EBITDA multiples",
        "investment/portfolio_metrics": "compute the sharpe ratio and alpha for this portfolio",
        "investment/private_equity_returns": "what is the IRR and MOIC on this private equity fund",
        "risk/value_at_risk": "calculate the 99% value at risk and expected shortfall",
        "risk/stress_testing": "run a stress test scenario on the trading book",
        "accounting/revenue_recognition": "assess the revenue recognition and accrual quality",
        "planning/retirement_goal_planning": "am i on track for retirement planning at my withdrawal rate",
        "forecasting/budget_variance_analysis": "do a budget variance analysis on price and volume",
        "forecasting/driver_based_forecast": "build a driver-based forecast for the SaaS revenue",
        "analysis/ratio_analysis": "run a ratio analysis on the income statement and balance sheet",
    }
    for recipe_stub, prompt in breadth.items():
        ctx, sk = domain_knowledge_context(prompt, skill_dir=PROPOSED_SKILL.parent)
        _require(sk is not None and sk.skill_id == "finance_credit_analysis", f"{prompt!r} should route to finance, got {sk}")
        _require(recipe_stub in ctx, f"{prompt!r} should retrieve {recipe_stub}, got: {ctx[:120]}")

    from skill_evaluator import evaluate_skill_scaffold

    results = evaluate_skill_scaffold("maya_skills/proposed/finance_credit_analysis.md")
    failed = [name for name, (status, _) in results.items() if status != "passed"]
    _require(not failed, f"finance skill failed scaffold checks: {failed}")


def _cloud_checks() -> None:
    skills = load_domain_skills(PROPOSED_SKILL.parent)
    # Breadth: each discipline must route to the cloud pack and pull its recipe.
    breadth = {
        "architecture/three_tier_web_app": "design a three-tier web app on AWS for 99.9% availability",
        "architecture/serverless_event_driven": "design a serverless event-driven architecture on GCP",
        "architecture/landing_zone_design": "set up a landing zone for our Azure subscriptions",
        "resilience/high_availability_dr": "what disaster recovery tier meets an RTO of 15 minutes",
        "cost/cost_optimization_review": "run a cloud cost optimization review on our monthly bill",
        "migration/migration_assessment": "plan our cloud migration with lift and shift to azure",
        "security/iam_least_privilege_review": "run an IAM least privilege review on the production account",
    }
    for recipe_stub, prompt in breadth.items():
        ctx, sk = domain_knowledge_context(prompt, skill_dir=PROPOSED_SKILL.parent)
        _require(sk is not None and sk.skill_id == "cloud_solution_architecture",
                 f"{prompt!r} should route to cloud, got {sk.skill_id if sk else None}")
        _require(recipe_stub in ctx, f"{prompt!r} should retrieve {recipe_stub}, got: {ctx[:120]}")
        _require("[source: docs/cloud/" in ctx, "cloud context must cite its source path")
    # Whole-recipe contract: limitations must travel with the design.
    dr_ctx, _ = domain_knowledge_context(
        "what disaster recovery tier meets an RTO of 15 minutes", skill_dir=PROPOSED_SKILL.parent
    )
    _require("limitations" in dr_ctx.lower(), "cloud recipes must retrieve whole (with limitations)")
    # Zainal's iMac hotfix 2026-06-12: provider-mapping rule must ride the
    # contract (the live three-tier answer skipped GCP/Azure until it did).
    three_tier_ctx, _ = domain_knowledge_context(
        "design a three-tier web app on AWS for an online store", skill_dir=PROPOSED_SKILL.parent
    )
    _require("include a compact mapping" in three_tier_ctx,
             "cloud provider-mapping rule missing from the answer contract")
    # Collision guard: device-protocol prompts stay with network_engineering.
    for prompt in (
        "create a vrf for customer A on the PE router",
        "design the network for a new branch campus",
        "how do I configure HSRP on the campus distribution boundary",
    ):
        matched = detect_domain_skill(prompt, skills)
        _require(matched is not None and matched.skill_id == "network_engineering",
                 f"{prompt!r} should stay with network, got {matched.skill_id if matched else None}")
    # Vetoes: consumer-cloud and weather phrasing must inject nothing.
    for prompt in (
        "back up my photos to icloud",
        "save this file to google drive",
        "will it be cloudy in penang tomorrow",
        "make a word cloud from this survey",
    ):
        silent, none_skill = domain_knowledge_context(prompt, skill_dir=PROPOSED_SKILL.parent)
        _require(silent == "" and none_skill is None, f"should stay silent: {prompt!r}")

    from skill_evaluator import evaluate_skill_scaffold

    results = evaluate_skill_scaffold("maya_skills/proposed/cloud_solution_architecture.md")
    failed = [name for name, (status, _) in results.items() if status != "passed"]
    _require(not failed, f"cloud skill failed scaffold checks: {failed}")


def _inert_until_active_checks() -> None:
    # Contract: retrieval reads ONLY the scanned directory. (Originally proven
    # with network_engineering in proposed/; since the 2026-06-12 promotion the
    # packs legitimately live in active/ too, so probe with a skill that exists
    # ONLY outside active/ — promotion-state-agnostic.)
    with tempfile.TemporaryDirectory(prefix="maya-domain-active-") as tmp:
        staging = Path(tmp)
        shutil.copy2(PROPOSED_SKILL, staging / "inert_probe_pack.md")
        skills = load_domain_skills(DEFAULT_SKILL_DIR)
        _require(
            all(skill.skill_id != "inert_probe_pack" for skill in skills),
            "un-promoted skill must stay inert in the active/ scan",
        )
        # ...and promoting it (simulated: scanning its directory) turns retrieval on.
        context, skill = domain_knowledge_context(
            "create a vrf for customer A",
            skill_dir=staging,
        )
        _require(skill is not None and "vrf" in context.lower(), "promoted skill should retrieve")


def main() -> None:
    _parsing_checks()
    _activation_checks()
    _retrieval_checks()
    _finance_checks()
    _cloud_checks()
    _inert_until_active_checks()
    print("skill_domain_smoke: ok")


if __name__ == "__main__":
    main()
