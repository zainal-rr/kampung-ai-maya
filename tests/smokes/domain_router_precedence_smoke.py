"""Deterministic smoke for Phase 5 routing fixes (2026-06-12 live findings).

Covers:
1. Router precedence: a strong domain-pack question with no explicit artifact
   format must NOT enter the semantic artifact router (the live hijack:
   "design the network for a new branch campus" was asked Word/Excel/PPT).
2. Artifact regressions: explicit format/deliverable words keep the artifact
   path even when a domain pack also matches.
3. Sticky follow-up helpers used by skill_registry.
4. Model output caps are env-tunable and no longer hardcoded at 1024
   (the /complex truncation finding).
"""

from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import contextlib
import os
import shutil
import tempfile
from pathlib import Path

import domain_knowledge
from maya_documents.artifact_semantic_resolver import (
    domain_question_precedence,
    resolve_semantic_artifact_intent,
)
from skill_registry import _followup_phrasing, _latest_domain_skill_id

_PACKS = ("network_engineering.md", "finance_credit_analysis.md", "cloud_solution_architecture.md")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


@contextlib.contextmanager
def _promoted_packs():
    """Simulate the live iMac state: the three packs promoted to active/.

    The precedence gate reads DEFAULT_SKILL_DIR (= maya_skills/active in
    production). Pointing it at a temp copy makes this smoke deterministic on
    machines where the packs are not promoted, without mutating the repo.
    """
    original = domain_knowledge.DEFAULT_SKILL_DIR
    with tempfile.TemporaryDirectory(prefix="maya-active-sim-") as tmp:
        active = Path(tmp)
        for name in _PACKS:
            shutil.copy2(Path("maya_skills") / "proposed" / name, active / name)
        domain_knowledge.DEFAULT_SKILL_DIR = active
        try:
            yield
        finally:
            domain_knowledge.DEFAULT_SKILL_DIR = original


def _precedence_checks() -> None:
    # Domain questions WITHOUT artifact words: must divert away from the router.
    diverted = (
        "design the network for a new branch campus",          # the live hijack
        "create a vrf for customer A on the PE router",
        "build a discounted cash flow valuation with WACC and terminal value",
        "what disaster recovery tier meets an RTO of 15 minutes",
        "design a three-tier web app on AWS for an online store",
    )
    for prompt in diverted:
        _require(domain_question_precedence(prompt), f"should divert to domain chat: {prompt!r}")
    # Explicit artifact asks: must KEEP the artifact path (Phase 4 contract).
    kept = (
        "make me a monthly budget tracker",                      # tracker
        "make an excel liquidity gap analysis for the institution",  # excel
        "make a powerpoint deck about disaster recovery",        # deck
        "write a word document proposal for the preference share issuance",  # document
        "write a report on the liquidity gap",                   # report (docx deliverable)
        "hello how are you today",                               # no domain, no artifact
    )
    for prompt in kept:
        _require(not domain_question_precedence(prompt), f"should NOT divert: {prompt!r}")


def _resolver_gate_checks() -> None:
    # The gate must fire deterministically BEFORE any provider call: resolver
    # returns None for the hijack prompt even with a fake API key present.
    os.environ.pop("MAYA_TEST_MODE", None)
    os.environ["XAI_API_KEY"] = "fake-key-never-called"
    try:
        with tempfile.TemporaryDirectory(prefix="maya-precedence-") as tmp:
            db = str(Path(tmp) / "smoke.db")
            result = asyncio.run(
                resolve_semantic_artifact_intent(db, "design the network for a new branch campus")
            )
            _require(result is None, f"hijack prompt must bypass the artifact router, got {result}")
    finally:
        os.environ.pop("XAI_API_KEY", None)


def _sticky_helper_checks() -> None:
    _require(_followup_phrasing("now assess the issuance from an investor's perspective"),
             "'now ...' should read as follow-up")
    _require(_followup_phrasing("what about the coverage ratio"), "'what about' should read as follow-up")
    _require(_followup_phrasing("is it still feasible"), "pronoun reference should read as follow-up")
    _require(not _followup_phrasing("make me a budget tracker"), "fresh request is not a follow-up")
    events = [
        {"skill_id": "office_documents"},
        {"skill_id": "domain:finance_credit_analysis"},
        {"skill_id": "domain:network_engineering"},
    ]
    _require(_latest_domain_skill_id(events) == "finance_credit_analysis",
             "latest domain id should be the most recent domain event")
    _require(_latest_domain_skill_id([{"skill_id": "office_documents"}]) == "",
             "no domain event -> empty sticky id")


def _plan_path_checks() -> None:
    # Zainal's iMac hotfix 2026-06-12: the banking /complex case contained
    # "It plans to raise 100 million..." and the old substring trigger
    # converted the QUESTION into a plan/review workflow. Plan routing now
    # requires an explicit ask for a plan.
    from maya_core.assistant_model_lanes import ModelLanes

    should_use = ModelLanes.should_use_plan_path
    banking = (
        "A non-deposit financial institution reports a loan book of 200 million. "
        "It plans to raise 100 million in Redeemable Preference Shares to cover the gap. "
        "Quantify the liquidity gap and assess the feasibility."
    )
    _require(not should_use(banking), "'it plans to raise' must NOT route to the plan lane")
    _require(not should_use("the company plans to expand into three markets"),
             "third-party 'plans to' wording must stay in the answer lane")
    for ask in (
        "make a plan for the kitchen renovation",
        "make me a plan for the migration",
        "write me a detailed plan for the launch",
        "give me a plan for the move",
        "prepare a plan for onboarding",
        "plan my week around the deadline",
        "draft an implementation plan for the rollout",
    ):
        _require(should_use(ask), f"explicit plan ask should route to plan lane: {ask!r}")


def _model_cap_checks() -> None:
    source = Path("models.py").read_text(encoding="utf-8")
    _require("MAYA_MIND_MAX_OUTPUT_TOKENS" in source, "Mind output cap must be env-tunable")
    _require("MAYA_STEWARD_MAX_TOKENS" in source, "Steward output cap must be env-tunable")
    _require('max_output_tokens=1024' not in source, "hardcoded 1024 Mind cap must be gone")
    _require('"max_tokens": 1024' not in source, "hardcoded 1024 Steward cap must be gone")


def main() -> None:
    with _promoted_packs():
        _precedence_checks()
        _resolver_gate_checks()
    _sticky_helper_checks()
    _plan_path_checks()
    _model_cap_checks()
    print("domain_router_precedence_smoke: ok")


if __name__ == "__main__":
    main()
