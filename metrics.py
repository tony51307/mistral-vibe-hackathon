from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from game import SeasonState


def agent_scoreboard(state: SeasonState) -> list[dict[str, Any]]:
    events = [event for result in state.history for event in result.events]
    by_agent: dict[str, list] = defaultdict(list)
    for event in events:
        by_agent[event.agent_id].append(event)

    rows = []
    for agent_id, agent in state.agents.items():
        agent_events = by_agent.get(agent_id, [])
        correct = sum(1 for event in agent_events if event.correct)
        entered = len(agent_events)
        reasoning_spend = sum(event.reasoning_cost for event in agent_events)
        prizes = sum(event.prize_received for event in agent_events)
        rows.append(
            {
                "agent": agent.name,
                "policy": agent.policy,
                "bankroll": round(agent.bankroll, 2),
                "entered": entered,
                "correct": correct,
                "accuracy": round(correct / entered, 2) if entered else 0,
                "reasoning_burn": round(reasoning_spend, 2),
                "prizes_won": round(prizes, 2),
                "reward_per_reasoning_dollar": round(prizes / reasoning_spend, 2)
                if reasoning_spend
                else 0,
                "eliminated": agent.eliminated,
            }
        )
    return rows


def economy_metrics(state: SeasonState) -> dict[str, Any]:
    events = [event for result in state.history for event in result.events]
    tier_counts = Counter(event.reasoning_tier for event in events)
    total_reasoning = sum(event.reasoning_cost for event in events)
    active_decisions = len(events)
    money_supply = sum(agent.bankroll for agent in state.agents.values()) + state.rollover

    return {
        "rounds_played": state.round_number,
        "money_supply": round(money_supply, 2),
        "unresolved_jackpot": round(state.rollover, 2),
        "average_reasoning_spend": round(total_reasoning / active_decisions, 2)
        if active_decisions
        else 0,
        "tier_distribution": dict(tier_counts),
        "rollover_rounds": sum(1 for result in state.history if result.rollover_out > 0),
    }


def bankroll_series(state: SeasonState) -> list[dict[str, Any]]:
    rows = []
    for result in state.history:
        for event in result.events:
            rows.append(
                {
                    "round": result.round_id,
                    "agent": state.agents[event.agent_id].name,
                    "bankroll": event.bankroll_after_round,
                }
            )
    return rows

