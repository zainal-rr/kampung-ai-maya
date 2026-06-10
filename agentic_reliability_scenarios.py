from __future__ import annotations

"""Scenario bank for live agentic (/complex + harness) reliability nights.

Each scenario is a scripted multi-turn conversation through HarnessRouter —
the same entry point Telegram and the iMac use. A fresh router instance is
created per turn, so every scenario also proves checkpoint persistence.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgenticTurn:
    text: str
    kind: str = "turn"  # turn | approve | decline | probe
    expect_contains: tuple[str, ...] = ()
    expect_not_contains: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgenticScenario:
    id: str
    title: str
    turns: tuple[AgenticTurn, ...]
    workflow_type: str = ""
    expect_artifact_ext: str = ""
    expect_approval: bool = False
    expect_final_status: str = ""
    min_events: int = 2
    goal_fragment: str = ""
    live_only: bool = False


def agentic_scenarios(only: str = "all") -> list[AgenticScenario]:
    if only == "all":
        return list(_SCENARIOS)
    return [scenario for scenario in _SCENARIOS if scenario.id == only]


_SCENARIOS = (
    AgenticScenario(
        "excel_budget",
        "Create an Excel artifact and recall it",
        (
            AgenticTurn("make an excel of a 3 day Penang food budget"),
            AgenticTurn("what files did you create", kind="probe", expect_contains=("artifact",)),
        ),
        workflow_type="document",
        expect_artifact_ext=".xlsx",
        expect_final_status="completed",
        goal_fragment="excel",
        live_only=True,
    ),
    AgenticScenario(
        "word_summary",
        "Create a Word artifact",
        (AgenticTurn("write a word document about the Penang trip checklist"),),
        workflow_type="document",
        expect_artifact_ext=".docx",
        expect_final_status="completed",
        goal_fragment="word",
        live_only=True,
    ),
    AgenticScenario(
        "presentation",
        "Create a PowerPoint artifact",
        (AgenticTurn("make presentation about Maya browser reliability results"),),
        workflow_type="document",
        expect_artifact_ext=".pptx",
        expect_final_status="completed",
        goal_fragment="presentation",
        live_only=True,
    ),
    AgenticScenario(
        "flight_followup_stop",
        "Browser workflow with follow-up and clean stop",
        (
            AgenticTurn("check flight to Penang on July 10", expect_contains=("stop before",)),
            AgenticTurn("make it cheaper", expect_contains=("continuing",)),
            AgenticTurn("stop workflow", expect_contains=("closed",)),
        ),
        workflow_type="browser",
        expect_final_status="cancelled",
        min_events=3,
        goal_fragment="flight",
    ),
    AgenticScenario(
        "hotel_safe_stop",
        "Hotel booking request stays research-only",
        (
            AgenticTurn("book me a hotel in Penang for July 10 to 12", expect_not_contains=("booked", "reservation confirmed")),
            AgenticTurn("stop workflow"),
        ),
        workflow_type="skill",
        expect_final_status="cancelled",
        goal_fragment="hotel",
    ),
    AgenticScenario(
        "self_heal_proposal",
        "Self-heal stays proposal-only with no code changes",
        (
            AgenticTurn("self heal the failing browser smoke", expect_contains=("proposal only",)),
            AgenticTurn("stop workflow"),
        ),
        workflow_type="self_heal",
        expect_final_status="cancelled",
        goal_fragment="self heal",
    ),
    AgenticScenario(
        "complex_gate_decline",
        "/complex execution workflow waits for approval; decline cancels it",
        (
            AgenticTurn("self heal maya and execute after approval", kind="seed_complex", expect_contains=("waiting for approval",)),
            AgenticTurn("no", kind="decline", expect_contains=("won't",)),
        ),
        workflow_type="self_heal",
        expect_approval=True,
        expect_final_status="cancelled",
        min_events=2,
    ),
    AgenticScenario(
        "complex_gate_approve",
        "/complex execution workflow resumes after approval",
        (
            AgenticTurn("self heal maya and execute after approval", kind="seed_complex", expect_contains=("waiting for approval",)),
            AgenticTurn("yes", kind="approve"),
        ),
        workflow_type="self_heal",
        expect_approval=True,
        min_events=3,
    ),
    AgenticScenario(
        "kill_and_resume",
        "Workflow survives a process restart and resumes from checkpoint",
        (
            AgenticTurn("check flight to Langkawi on August 2"),
            AgenticTurn("where did we stop", kind="probe", expect_contains=("flight",)),
            AgenticTurn("stop workflow"),
        ),
        workflow_type="browser",
        expect_final_status="cancelled",
        goal_fragment="langkawi",
    ),
    AgenticScenario(
        "multi_workflow_resume",
        "Two active workflows are listed and selectable",
        (
            AgenticTurn("make an excel of july spending"),
            AgenticTurn("check flight to Kuching on August 9"),
            AgenticTurn("what are you working on", kind="probe", expect_contains=("flight",)),
            AgenticTurn("stop workflow"),
        ),
        workflow_type="document",
        goal_fragment="kuching",
        live_only=True,
    ),
    AgenticScenario(
        "stop_when_idle",
        "Stopping with nothing active is answered honestly",
        (AgenticTurn("stop workflow", expect_contains=("no active",)),),
        min_events=0,
    ),
    AgenticScenario(
        "status_probe",
        "Workflow status is reported during an active run",
        (
            AgenticTurn("check flight to Ipoh on August 21"),
            AgenticTurn("workflow status", kind="probe", expect_contains=("flight",)),
            AgenticTurn("stop workflow"),
        ),
        workflow_type="browser",
        expect_final_status="cancelled",
        goal_fragment="ipoh",
    ),
    AgenticScenario(
        "screen_workflow",
        "Screen workflow starts and answers from visible context",
        (
            AgenticTurn("look at my screen and tell me what is open"),
            AgenticTurn("stop workflow"),
        ),
        workflow_type="screen",
        goal_fragment="screen",
        live_only=True,
    ),
)
