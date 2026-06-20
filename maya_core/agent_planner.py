from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanStep:
    name: str
    description: str


class AgentPlanner:
    def build_plan(self, task: dict[str, str | int | None]) -> list[PlanStep]:
        action_type = str(task["action_type"])
        if action_type == "follow_up":
            return [
                PlanStep("prepare_message", "Prepare reminder message"),
                PlanStep("deliver_message", "Deliver reminder through the requested channel"),
            ]
        if action_type == "send_message":
            return [
                PlanStep("prepare_message", "Prepare the outbound message"),
                PlanStep("deliver_message", "Deliver the outbound message"),
            ]
        if action_type == "create_skill_scaffold":
            return [
                PlanStep("scaffold_skill", "Draft and write a new Maya skill scaffold"),
            ]
        if action_type == "summarize_history":
            return [
                PlanStep("collect_summary", "Summarize the recent interaction history"),
                PlanStep("deliver_message", "Deliver the prepared summary"),
            ]
        if action_type == "scheduled_briefing":
            return [
                PlanStep("prepare_message", "Prepare the scheduled briefing"),
                PlanStep("deliver_message", "Deliver the scheduled briefing"),
            ]
        if action_type == "digest_omi":
            return [PlanStep("queue_digest", "Queue Omi digest review for later summarization")]
        return [PlanStep("unsupported", "Unsupported action type")]

    def verify_step(
        self,
        task: dict[str, str | int | None],
        step: PlanStep,
        context: dict[str, str | bool],
    ) -> tuple[bool, str]:
        if step.name in {"prepare_message", "collect_summary"}:
            message = str(context.get("message") or "").strip()
            return (bool(message), "Prepared message is ready." if message else "No prepared message was produced.")

        if step.name == "deliver_message":
            delivered = bool(context.get("delivered"))
            return (
                delivered,
                "Message delivery confirmed." if delivered else "Message delivery did not confirm.",
            )

        if step.name == "queue_digest":
            queued = bool(context.get("queued"))
            return (queued, "Digest queued." if queued else "Digest queue was not confirmed.")

        if step.name == "scaffold_skill":
            path = str(context.get("scaffold_path") or "").strip()
            return (bool(path), "Skill scaffold created." if path else "Skill scaffold path was not created.")

        return False, f"No verifier for step {step.name}."
