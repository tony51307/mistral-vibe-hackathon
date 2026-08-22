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
        score = self._score(context)

        if agreement == "2/2" and risk == "low":
            tier = baseline
            level = "LOW"
            reason = "stable routing decision and low economic risk"
        elif agreement == "1/2" and risk == "high":
            tier = "xhigh" if score % 5 == 0 else "high"
            level = "HIGH"
            reason = "routing disagreement under high economic risk"
        elif agreement == "1/2" and risk == "medium":
            tier = "high"
            level = "HIGH"
            reason = "routing disagreement on a medium-risk decision"
        elif agreement == "1/2":
            tier = "medium"
            level = "HIGH"
            reason = "routing disagreement"
        elif risk == "high":
            tier = "high" if score % 3 == 0 else max((baseline, "medium"), key=TIER_ORDER.index)
            level = "HIGH"
            reason = "stable decision but high economic risk"
        elif risk == "medium" and score % 4 == 0:
            tier = "medium"
            level = "LOW"
            reason = "moderate risk justifies a middle tier"
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
                "category": context.category,
            },
        )

    def _baseline_decision(self, context: RoutingContext) -> str:
        score = self._score(context)
        if context.pot >= 100:
            return "high"
        if context.bankroll_after_entry <= 14:
            return "none"
        if context.problem.category in {"math", "logic"} and score % 5 != 0:
            return "low"
        if context.problem.category in {"probability", "algorithms"}:
            return "medium"
        return "low" if score % 3 else "medium"

    def _critical_decision(self, context: RoutingContext) -> str:
        score = self._score(context)
        if context.pot >= 100:
            return "xhigh"
        if context.bankroll_after_entry <= 14:
            return "low" if context.pot >= 70 else "none"
        if context.problem.category in {"probability", "algorithms"} and score % 4 != 1:
            return "high"
        if context.problem.category in {"physics", "computer science"} and score % 3 == 0:
            return "high"
        if context.problem.category in {"math", "logic"} and score % 4 != 0:
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

    def _score(self, context: RoutingContext) -> int:
        fingerprint = hashlib.sha256(
            f"{context.agent_id}:{context.problem.id}:{context.round_number}:{context.pot}".encode()
        ).hexdigest()
        return int(fingerprint[:8], 16) % 100
