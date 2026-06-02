from __future__ import annotations

from maya_tool_registry import MayaToolRegistry, MayaToolSpec, default_maya_tool_registry


def main() -> None:
    registry = default_maya_tool_registry()
    _require(registry.get("docx.create") is not None, "docx tool missing")
    _require(registry.get("repo.apply_patch") is not None, "repo apply tool missing")
    _require(registry.permission_for("docx.create") == "allow", "docx should be auto-allowed")
    _require(registry.permission_for("repo.apply_patch") == "confirm", "repo patch should require approval")
    _require(registry.permission_for("mcp.call") == "confirm", "mcp call should require approval")
    _require(not registry.require("telegram.send_file").replay_safe, "send-file should not be replay safe")

    document_tools = registry.list(owner_lane="documents")
    _require([tool.name for tool in document_tools] == ["docx.create", "pptx.create", "xlsx.create"], "doc list wrong")

    custom = MayaToolRegistry()
    custom.register(MayaToolSpec("demo.read", "Read demo state"))
    _require(custom.permission_for("demo.read") == "allow", "custom read tool permission wrong")
    print("maya_tool_registry_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
