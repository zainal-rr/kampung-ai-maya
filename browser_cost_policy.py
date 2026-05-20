from __future__ import annotations

from dataclasses import dataclass


FLASH_COST = 0.001
PRO_COST = 0.01
DEFAULT_BROWSER_BUDGET = 0.05


@dataclass(frozen=True)
class BrowserCostDecision:
    lane: str
    allowed: bool
    estimated_cost: float
    reason: str
    needs_confirmation: bool = False


def local_decision() -> BrowserCostDecision:
    return BrowserCostDecision("local", True, 0.0, "local Chrome DOM and macOS screen path")


def escalation_decision(
    *,
    reason: str,
    current_cost: float = 0.0,
    confidence: float = 1.0,
    careful: bool = False,
) -> BrowserCostDecision:
    lowered = reason.lower()
    if careful or confidence < 0.6 or any(word in lowered for word in ("tiny text", "low confidence", "double check")):
        return _gate("gemini_pro", PRO_COST, current_cost, "careful visual browser check")
    if any(word in lowered for word in ("messy", "visual", "compare", "screen", "cluttered")):
        return _gate("gemini_flash", FLASH_COST, current_cost, "summarize messy visible browser page")
    return local_decision()


def _gate(lane: str, cost: float, current_cost: float, reason: str) -> BrowserCostDecision:
    projected = current_cost + cost
    return BrowserCostDecision(
        lane,
        projected <= DEFAULT_BROWSER_BUDGET,
        cost,
        reason,
        needs_confirmation=projected > DEFAULT_BROWSER_BUDGET,
    )
