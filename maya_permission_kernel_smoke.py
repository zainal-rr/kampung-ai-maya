from __future__ import annotations

from maya_permission_kernel import MayaPermissionKernel


def main() -> None:
    kernel = MayaPermissionKernel()
    _require(kernel.check("docx.create").decision == "allow", "docx should be allowed")
    _require(kernel.check("repo.apply_patch").decision == "confirm", "repo patch should confirm")
    _require(kernel.check("unknown.tool").decision == "confirm", "unknown tool should confirm")
    denied = kernel.check("telegram.send_file", args={"text": "my api key is sk-abcdefghijklmnopqrstuvwxyz"})
    _require(denied.decision == "deny", "secret exposure should be denied")
    _require(not kernel.check("browser.click").replay_safe, "click should not be replay safe")
    print("maya_permission_kernel_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
