from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from economy import TIER_ORDER, affordable_tiers, clamp_tier_to_bankroll
from problems import Problem


@dataclass(frozen=True)
class RoutingContext:
    agent_id: str
    category: str
    problem: Problem
    bankroll_after_entry: float
    pot: float
    round_number: int
    public_messages: dict[str, str]
    opponent_history: dict[str, dict]
    available_reasoning_tiers: list[str]
    strategy_memory: list[str] = field(default_factory=list)
    rollover_chain: int = 0


@dataclass(frozen=True)
class RoutingDecision:
    reasoning_tier: str
    autothink_level: str
    decision_agreement: str
    risk: str
    reason: str
    baseline_decision: str
    critical_perspective_decision: str
    probe_cost_tokens: int
    estimated_deep_budget_tokens: int
    trace: dict


class AutoThinkingAdapter:
    """Drop-in boundary for the later Vibe AutoThink implementation."""

    def route(self, context: RoutingContext) -> RoutingDecision:
        raise NotImplementedError


class StubAutoThinkingAdapter(AutoThinkingAdapter):
    """Deterministic approximation of the AutoThink MVP for offline demos."""

    def route(self, context: RoutingContext) -> RoutingDecision:
        baseline = self._baseline_decision(context)
        critical = self._critical_decision(context)
        agreement = "2/2" if baseline == critical else "1/2"
        risk = self._risk(context)

        if agreement == "2/2" and risk == "low":
            tier = baseline
            level = "LOW"
            reason = "stable routing decision and low economic risk"
        elif agreement == "1/2" and risk == "high":
            tier = "high"
            level = "HIGH"
            reason = "routing disagreement under high economic risk"
        elif agreement == "1/2":
            tier = "medium"
            level = "HIGH"
            reason = "routing disagreement"
        elif risk == "high":
            tier = max((baseline, "medium"), key=TIER_ORDER.index)
            level = "HIGH"
            reason = "stable decision but high economic risk"
        else:
            tier = baseline
            level = "LOW"
            reason = "stable enough for low-cost reasoning"

        tier = clamp_tier_to_bankroll(tier, context.bankroll_after_entry)
        return RoutingDecision(
            reasoning_tier=tier,
            autothink_level=level,
            decision_agreement=agreement,
            risk=risk,
            reason=reason,
            baseline_decision=baseline,
            critical_perspective_decision=critical,
            probe_cost_tokens=310,
            estimated_deep_budget_tokens=3000 if level == "HIGH" else 0,
            trace={
                "affordable_tiers": affordable_tiers(context.bankroll_after_entry),
                "pot": context.pot,
                "rollover_chain": context.rollover_chain,
                "hidden_difficulty_visible_to_dealer_only": context.problem.hidden_difficulty,
            },
        )

    def _baseline_decision(self, context: RoutingContext) -> str:
        if context.pot >= 100:
            return "high"
        if context.problem.category in {"math", "logic"}:
            return "low"
        return "medium"

    def _critical_decision(self, context: RoutingContext) -> str:
        fingerprint = hashlib.sha256(
            f"{context.agent_id}:{context.problem.id}:{context.round_number}".encode()
        ).hexdigest()
        unstable = int(fingerprint[:2], 16) % 3 == 0
        if context.pot >= 100:
            return "xhigh"
        if context.problem.hidden_difficulty in {"hard", "very hard"} or unstable:
            return "high"
        if context.problem.category in {"math", "logic"}:
            return "low"
        return "medium"

    def _risk(self, context: RoutingContext) -> str:
        if context.pot >= 100 or context.rollover_chain > 0:
            return "high"
        if context.bankroll_after_entry <= 12:
            return "high"
        if context.problem.category in {"probability", "algorithms"}:
            return "medium"
        return "low"

