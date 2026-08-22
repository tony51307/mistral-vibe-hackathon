from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AgentRoundEvent:
    season_id: str
    round_id: int
    problem_id: str
    category: str
    hidden_difficulty: str
    correct_answer: str
    agent_id: str
    bankroll_before: float
    public_message: str
    entry_paid: float
    reasoning_tier: str
    reasoning_cost: float
    bankroll_after_reasoning: float
    submitted_answer: str
    correct: bool
    prize_received: float
    bankroll_after_round: float
    pot_before: float
    dealer_contribution: float
    rollover_in: float
    rollover_out: float
    number_correct: int
    show_hand: bool
    routing_trace: dict[str, Any]
    model_telemetry: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def events_to_json(events: list[AgentRoundEvent]) -> str:
    return json.dumps([event.to_dict() for event in events], indent=2)

