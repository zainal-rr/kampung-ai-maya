from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LaneClearance:
    lane_id: str
    owner: str
    sees_raw_untrusted_content: bool
    sees_structured_facts: bool
    can_propose_effects: bool
    can_authorize_effects: bool
    can_execute_effects: bool
    kernel_gated_effects: bool
    can_disclose_private_data: bool
    disclosure_gated: bool
    notes: str


CLEARANCE_MAP: tuple[LaneClearance, ...] = (
    LaneClearance(
        lane_id="mind",
        owner="The Mind / GPT",
        sees_raw_untrusted_content=False,
        sees_structured_facts=True,
        can_propose_effects=True,
        can_authorize_effects=False,
        can_execute_effects=False,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Explicit complex/planner lane. Control prompts receive PlannerFacts, not raw observations.",
    ),
    LaneClearance(
        lane_id="sight",
        owner="The Senses / Gemini",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=False,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Reader/research lane. Reads content and emits summaries/facts through Maya gates.",
    ),
    LaneClearance(
        lane_id="steward",
        owner="The Steward / Claude",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=False,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Reviewer lane. Recommendations are non-executing and still pass through Maya.",
    ),
    LaneClearance(
        lane_id="news_pulse",
        owner="TheNews/The Pulse / Grok",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=False,
        kernel_gated_effects=True,
        can_disclose_private_data=True,
        disclosure_gated=True,
        notes="Responder/voice lane. Output is destination scoped; private/external disclosure policies still apply.",
    ),
    LaneClearance(
        lane_id="artisan",
        owner="The Artisan / Codex",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=True,
        can_authorize_effects=False,
        can_execute_effects=True,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Worker lane. Effectful work is brokered/kernel-gated and reviewed where required.",
    ),
    LaneClearance(
        lane_id="harness.plan_with_llm",
        owner="Harness control prompt",
        sees_raw_untrusted_content=False,
        sees_structured_facts=True,
        can_propose_effects=True,
        can_authorize_effects=False,
        can_execute_effects=False,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Planning prompt uses PlannerFacts only; proposed effects still go through the kernel.",
    ),
    LaneClearance(
        lane_id="harness.choose_next_action",
        owner="Harness control prompt",
        sees_raw_untrusted_content=False,
        sees_structured_facts=True,
        can_propose_effects=True,
        can_authorize_effects=False,
        can_execute_effects=False,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Action selection prompt uses PlannerFacts only; execution is kernel-gated.",
    ),
    LaneClearance(
        lane_id="harness.verify_goal",
        owner="Harness control prompt",
        sees_raw_untrusted_content=False,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=False,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Verifier sees facts and latest result, fails closed, and cannot execute tools.",
    ),
    LaneClearance(
        lane_id="harness.synthesize_final_answer",
        owner="Harness answer prompt",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=False,
        kernel_gated_effects=True,
        can_disclose_private_data=True,
        disclosure_gated=True,
        notes="Answer synthesis may read content as answer material only. Output is not trusted planner context.",
    ),
    LaneClearance(
        lane_id="telegram.router",
        owner="Telegram dispatch/router",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=True,
        can_authorize_effects=False,
        can_execute_effects=True,
        kernel_gated_effects=True,
        can_disclose_private_data=True,
        disclosure_gated=True,
        notes="Owner transport is not owner content. Router effects route through W7/provenance gates and confirmations.",
    ),
    LaneClearance(
        lane_id="telegram.memory_write",
        owner="Telegram memory route",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=True,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Persistent writes require owner-authored content; relayed email/web/page/file/meeting content is reference-only untrusted.",
    ),
    LaneClearance(
        lane_id="telegram.rewrite_candidate",
        owner="Telegram rewrite route",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=True,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Transient rewrite candidates exclude sensitive replies and relayed external content.",
    ),
    LaneClearance(
        lane_id="telegram.skill_scaffold",
        owner="Telegram skill scaffold route",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=True,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Skill scaffold tasks are confirmation-gated and relayed external content cannot queue scaffolds.",
    ),
    LaneClearance(
        lane_id="telegram.document_route",
        owner="Telegram document/artifact route",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=True,
        kernel_gated_effects=True,
        can_disclose_private_data=False,
        disclosure_gated=True,
        notes="Artifact creation stays in Maya-owned paths and private/disclosure requests are gated before document routing.",
    ),
    LaneClearance(
        lane_id="telegram.private_disclosure_guard",
        owner="Telegram private disclosure guard",
        sees_raw_untrusted_content=True,
        sees_structured_facts=True,
        can_propose_effects=False,
        can_authorize_effects=False,
        can_execute_effects=False,
        kernel_gated_effects=True,
        can_disclose_private_data=True,
        disclosure_gated=True,
        notes="Private/saved/medical/bank/password disclosure requests hard-deny or require owner-scoped approval before output.",
    ),
)


def validate_clearance_map(lanes: tuple[LaneClearance, ...] = CLEARANCE_MAP) -> list[str]:
    issues: list[str] = []
    seen = {lane.lane_id for lane in lanes}
    required = {
        "mind",
        "sight",
        "steward",
        "news_pulse",
        "artisan",
        "harness.plan_with_llm",
        "harness.choose_next_action",
        "harness.verify_goal",
        "harness.synthesize_final_answer",
        "telegram.router",
        "telegram.memory_write",
        "telegram.rewrite_candidate",
        "telegram.skill_scaffold",
        "telegram.document_route",
        "telegram.private_disclosure_guard",
    }
    missing = sorted(required - seen)
    if missing:
        issues.append(f"missing clearance rows: {', '.join(missing)}")
    for lane in lanes:
        if (
            lane.sees_raw_untrusted_content
            and (lane.can_authorize_effects or lane.can_execute_effects)
            and not lane.kernel_gated_effects
        ):
            issues.append(f"{lane.lane_id}: raw untrusted content can reach ungated effects")
        if lane.can_disclose_private_data and not lane.disclosure_gated:
            issues.append(f"{lane.lane_id}: private disclosure is not gated")
    return issues


def disclosure_gate_confirmed_for_answer_lanes(lanes: tuple[LaneClearance, ...] = CLEARANCE_MAP) -> bool:
    answer_lanes = [
        lane
        for lane in lanes
        if lane.lane_id in {"news_pulse", "harness.synthesize_final_answer"}
    ]
    return bool(answer_lanes) and all(lane.disclosure_gated for lane in answer_lanes)
