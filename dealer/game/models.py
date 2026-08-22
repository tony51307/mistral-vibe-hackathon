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
    max_rollover_chain: int = 3
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
            self.max_rollover_chain,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("game constants must be positive")
        if set(self.reasoning_prices_cents) != set(ReasoningTier):
            raise ValueError("reasoning price map must define every tier exactly once")
        if any(value <= 0 for value in self.reasoning_prices_cents.values()):
            raise ValueError("reasoning prices must be positive")

    @classmethod
    def for_table_size(cls, initial_agent_count: int, **overrides: Any) -> GameConfig:
        """Build the V1 economy once from the initial 2-to-10 seat count."""
        if (
            isinstance(initial_agent_count, bool)
            or not isinstance(initial_agent_count, int)
            or not 2 <= initial_agent_count <= 10
        ):
            raise ValueError("initial_agent_count must be between 2 and 10")
        if "dealer_contribution_cents" in overrides:
            raise ValueError("dealer contribution is derived from the initial table size")
        return cls(
            dealer_contribution_cents=300 * initial_agent_count,
            **overrides,
        )


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
    reference_reasoning_tier: ReasoningTier | None = None
    round_role: str | None = None


@dataclass(frozen=True)
class Agenda:
    strategy_number: int
    name: str
    objective: str
    rounds: tuple[AgendaRound, ...]
    showcase_bias: bool = False
    dynamic_advantage: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgendaCatalog:
    schema_version: str
    agendas: dict[int, Agenda]
    sha256: str
    path: Path


@dataclass(frozen=True)
class TableMode:
    mode_id: str
    name: str
    initial_agent_count: int
    recommended_agenda_strategy: int
    use_cases: tuple[str, ...]

    def default_player_ids(self) -> tuple[str, ...]:
        return tuple(f"agent_{seat}" for seat in range(1, self.initial_agent_count + 1))


@dataclass(frozen=True)
class TableCatalog:
    schema_version: str
    default_mode: str
    modes: dict[str, TableMode]
    sha256: str
    path: Path

    def get(self, mode_id: str | None = None) -> TableMode:
        selected = mode_id or self.default_mode
        try:
            return self.modes[selected]
        except KeyError as exc:
            raise ValueError(f"unknown table mode {selected!r}") from exc


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
