from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Phase(str, Enum):
    CATEGORY_REVEAL = "CATEGORY_REVEAL"
    ENTRY = "ENTRY"
    TABLE_TALK = "TABLE_TALK"
    PROBLEM_REVEAL = "PROBLEM_REVEAL"
    ROUTING = "ROUTING"
    SOLVING = "SOLVING"
    JUDGING = "JUDGING"
    PAYOUT = "PAYOUT"
    ROUND_COMPLETE = "ROUND_COMPLETE"


class ReasoningTier(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


TIER_ORDER = tuple(ReasoningTier)


@dataclass(frozen=True)
class GameConfig:
    starting_bankroll_cents: int = 8_000
    entry_fee_cents: int = 1_000
    dealer_contribution_cents: int = 1_200
    season_rounds: int = 25
    message_max_chars: int = 100
    reasoning_prices_cents: dict[ReasoningTier, int] = field(
        default_factory=lambda: {
            ReasoningTier.NONE: 100,
            ReasoningTier.LOW: 200,
            ReasoningTier.MEDIUM: 300,
            ReasoningTier.HIGH: 500,
            ReasoningTier.XHIGH: 900,
        }
    )

    def __post_init__(self) -> None:
        positive = (
            self.starting_bankroll_cents,
            self.entry_fee_cents,
            self.dealer_contribution_cents,
            self.season_rounds,
            self.message_max_chars,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("game constants must be positive")
        if set(self.reasoning_prices_cents) != set(ReasoningTier):
            raise ValueError("reasoning price map must define every tier exactly once")
        if any(value <= 0 for value in self.reasoning_prices_cents.values()):
            raise ValueError("reasoning prices must be positive")


@dataclass(frozen=True)
class ProblemBank:
    schema_version: str
    name: str
    problems: dict[str, dict[str, Any]]
    sha256: str
    path: Path


@dataclass(frozen=True)
class AgendaRound:
    round_number: int
    problem_id: str
    category: str
    dealer_difficulty: str
    guessability: str


@dataclass(frozen=True)
class Agenda:
    strategy_number: int
    name: str
    objective: str
    rounds: tuple[AgendaRound, ...]


@dataclass(frozen=True)
class AgendaCatalog:
    schema_version: str
    agendas: dict[int, Agenda]
    sha256: str
    path: Path


@dataclass
class PlayerState:
    agent_id: str
    bankroll_cents: int


@dataclass
class PlayerRound:
    agent_id: str
    bankroll_before_cents: int
    entry_paid_cents: int = 0
    show_hand: bool = False
    public_message: str = ""
    public_message_display: str = ""
    bankroll_after_entry_cents: int = 0
    router_tier: str | None = None
    reasoning_price_cents: int = 0
    router_fallback: bool = False
    router_attempts: int = 0
    submitted_answer: str | None = None
    correct: bool | None = None
    prize_received_cents: int = 0
    bankroll_after_round_cents: int | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JudgeResult:
    correct: bool
    parsed_value: int | float | str | bool | None
    validator_kind: str
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "correct": self.correct,
            "parsed_value": self.parsed_value,
            "validator_kind": self.validator_kind,
            "error": self.error,
        }
