from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from maya_core.permission_policy import action_permission


@dataclass(frozen=True)
class MayaToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    permission_scope: str = "follow_up"
    side_effect_level: str = "read"
    approval_required: bool = False
    cost_risk: str = "none"
    replay_safe: bool = True
    owner_lane: str = "local"

    def permission(self, content: str = "") -> str:
        decision = action_permission(self.permission_scope, content)
        if self.approval_required and decision == "allow":
            return "confirm"
        return decision


class MayaToolRegistry:
    def __init__(self):
        self._tools: dict[str, MayaToolSpec] = {}

    def register(self, spec: MayaToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> MayaToolSpec | None:
        return self._tools.get(name)

    def require(self, name: str) -> MayaToolSpec:
        spec = self.get(name)
        if not spec:
            raise KeyError(f"Unknown Maya tool: {name}")
        return spec

    def list(self, *, owner_lane: str | None = None) -> list[MayaToolSpec]:
        specs = list(self._tools.values())
        if owner_lane:
            specs = [spec for spec in specs if spec.owner_lane == owner_lane]
        return sorted(specs, key=lambda spec: spec.name)

    def permission_for(self, name: str, content: str = "") -> str:
        return self.require(name).permission(content)


def default_maya_tool_registry() -> MayaToolRegistry:
    registry = MayaToolRegistry()
    for spec in _DEFAULT_TOOLS:
        registry.register(spec)
    return registry


def schema(**properties: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {key: {"type": value} for key, value in properties.items()},
    }


_DEFAULT_TOOLS = (
    MayaToolSpec(
        "screen.capture",
        "Capture or inspect the current screen state.",
        output_schema=schema(summary="string"),
        permission_scope="follow_up",
        side_effect_level="read",
        owner_lane="sight",
    ),
    MayaToolSpec(
        "browser.inspect",
        "Read visible browser state without clicking or submitting.",
        input_schema=schema(url="string"),
        permission_scope="browse_web",
        side_effect_level="read",
        cost_risk="low",
        owner_lane="sight",
    ),
    MayaToolSpec(
        "browser.click",
        "Click a browser target. Sensitive clicks require confirmation.",
        input_schema=schema(target="string"),
        permission_scope="browser_click",
        side_effect_level="write",
        replay_safe=False,
        owner_lane="sight",
    ),
    MayaToolSpec(
        "file.create",
        "Create a local file inside an allowed Maya workspace.",
        input_schema=schema(path="string"),
        permission_scope="create_file",
        side_effect_level="write",
        replay_safe=False,
    ),
    MayaToolSpec(
        "docx.create",
        "Create a Word document through the artifact quality pipeline.",
        input_schema=schema(topic="string"),
        permission_scope="create_document",
        side_effect_level="write",
        cost_risk="medium",
        replay_safe=False,
        owner_lane="documents",
    ),
    MayaToolSpec(
        "xlsx.create",
        "Create an Excel workbook through the artifact quality pipeline.",
        input_schema=schema(topic="string"),
        permission_scope="create_document",
        side_effect_level="write",
        cost_risk="medium",
        replay_safe=False,
        owner_lane="documents",
    ),
    MayaToolSpec(
        "pptx.create",
        "Create a PowerPoint deck through the artifact quality pipeline.",
        input_schema=schema(topic="string"),
        permission_scope="create_presentation",
        side_effect_level="write",
        cost_risk="high",
        replay_safe=False,
        owner_lane="documents",
    ),
    MayaToolSpec(
        "memory.write",
        "Write a canonical memory item.",
        input_schema=schema(content="string"),
        permission_scope="follow_up",
        side_effect_level="write",
        replay_safe=False,
        owner_lane="memory",
    ),
    MayaToolSpec(
        "skill.activate",
        "Activate or select a Maya skill standard.",
        input_schema=schema(skill_id="string"),
        permission_scope="follow_up",
        side_effect_level="write",
        owner_lane="skills",
    ),
    MayaToolSpec(
        "mcp.call",
        "Call a configured MCP capability.",
        input_schema=schema(server="string", tool="string"),
        permission_scope="run_command",
        side_effect_level="external",
        approval_required=True,
        cost_risk="medium",
        replay_safe=False,
        owner_lane="artisan",
    ),
    MayaToolSpec(
        "blender.create_model",
        "Create local Blender source and exported 3D files.",
        input_schema=schema(prompt="string"),
        permission_scope="create_file",
        side_effect_level="write",
        cost_risk="medium",
        replay_safe=False,
        owner_lane="artisan",
    ),
    MayaToolSpec(
        "repo.apply_patch",
        "Apply proposed code changes to a repository working tree.",
        input_schema=schema(repo_path="string"),
        permission_scope="apply_code_patch",
        side_effect_level="repo_write",
        approval_required=True,
        replay_safe=False,
        owner_lane="artisan",
    ),
    MayaToolSpec(
        "telegram.send_file",
        "Attach a generated file to Telegram.",
        input_schema=schema(path="string"),
        permission_scope="share_file",
        side_effect_level="external",
        approval_required=True,
        replay_safe=False,
        owner_lane="telegram",
    ),
)
