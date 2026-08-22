from __future__ import annotations

import argparse
from copy import deepcopy
import html
import json
from pathlib import Path
from typing import Any, Mapping

from .agent_config import AgentCatalog, load_agent_catalog
from .economy import affordable_tiers, highest_affordable_tier, split_pot
from .event_log import JsonlEventLog
from .judge import judge_answer
from .loaders import load_agendas, load_problem_bank, load_table_modes, public_problem
from .models import (
    AgendaCatalog,
    AgendaRound,
    GameConfig,
    Phase,
    PlayerRound,
    PlayerState,
    ProblemBank,
    ReasoningTier,
    TableCatalog,
    TIER_ORDER,
)
from .reasoning_provider import REASONING_MAPPING_VERSION, Router, Solver, reasoning_config
from .rotation import AgendaExhausted, AgendaRotation


class InvalidPhase(RuntimeError):
    pass


class SeasonComplete(RuntimeError):
    def __init__(self, message: str, result: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.result = dict(result or {})


class DealerGame:
    """Deterministic, provider-agnostic V1 dealer state machine.

    Routers and solvers are injected callables. The dealer owns hidden data,
    economy mutations, answer validation, payout, and the JSONL audit record.
    """

    def __init__(
        self,
        *,
        player_ids: list[str] | tuple[str, ...],
        problem_bank: ProblemBank,
        agenda_catalog: AgendaCatalog,
        strategy_number: int,
        seed: int,
        season_id: str = "s001",
        config: GameConfig | None = None,
        output_path: str | Path | None = None,
        model_identifier: str = "unconfigured",
        code_version: str = "working-tree",
        table_mode_id: str = "custom",
        table_config_sha256: str | None = None,
        agent_roster_id: str | None = None,
        agent_config_sha256: str | None = None,
        agent_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    ):
        if not player_ids or len(set(player_ids)) != len(player_ids):
            raise ValueError("player_ids must be a non-empty unique sequence")
        if strategy_number not in agenda_catalog.agendas:
            raise ValueError(f"unknown agenda strategy {strategy_number}")
        self.initial_agent_count = len(player_ids)
        self.config = config or GameConfig.for_table_size(self.initial_agent_count)
        self.problem_bank = problem_bank
        self.agenda_catalog = agenda_catalog
        self.agenda = agenda_catalog.agendas[strategy_number]
        self.rotation = AgendaRotation(self.agenda, self.config.season_rounds)
        self.seed = seed
        self.season_id = season_id
        self.model_identifier = model_identifier
        self.code_version = code_version
        self.table_mode_id = table_mode_id
        self.table_config_sha256 = table_config_sha256
        self.agent_roster_id = agent_roster_id
        self.agent_config_sha256 = agent_config_sha256
        self.agent_metadata = {
            agent_id: dict(metadata)
            for agent_id, metadata in (agent_metadata or {}).items()
        }
        if self.agent_metadata and set(self.agent_metadata) != set(player_ids):
            raise ValueError("agent metadata must match every player ID exactly")
        self.players = {
            agent_id: PlayerState(agent_id, self.config.starting_bankroll_cents)
            for agent_id in player_ids
        }
        self.phase = Phase.CATEGORY_REVEAL
        self.rollover_cents = 0
        self.rollover_chain = 0
        self._event_log = JsonlEventLog(output_path) if output_path else None
        self._agenda_round: AgendaRound | None = None
        self._problem: dict[str, Any] | None = None
        self._round_players: dict[str, PlayerRound] = {}
        self._pot_cents = 0
        self._rollover_in_cents = 0
        self._entry_total_cents = 0
        self._winner_ids: list[str] = []
        self._judge_results: dict[str, dict[str, Any]] = {}
        self._last_event: dict[str, Any] | None = None
        self._public_problem_payloads: dict[str, dict[str, Any]] = {}
        self._season_result: dict[str, Any] | None = None
        self._public_history: list[dict[str, Any]] = []

    @classmethod
    def from_table_mode(
        cls,
        *,
        table_catalog: TableCatalog,
        mode_id: str | None,
        problem_bank: ProblemBank,
        agenda_catalog: AgendaCatalog,
        seed: int,
        player_ids: list[str] | tuple[str, ...] | None = None,
        strategy_number: int | None = None,
        **kwargs: Any,
    ) -> DealerGame:
        mode = table_catalog.get(mode_id)
        selected_ids = tuple(player_ids) if player_ids is not None else mode.default_player_ids()
        if len(selected_ids) != mode.initial_agent_count:
            raise ValueError(
                f"table mode {mode.mode_id!r} requires {mode.initial_agent_count} player IDs"
            )
        if "config" in kwargs:
            raise ValueError("table modes derive their GameConfig; use the direct constructor to override it")
        return cls(
            player_ids=selected_ids,
            problem_bank=problem_bank,
            agenda_catalog=agenda_catalog,
            strategy_number=(
                mode.recommended_agenda_strategy
                if strategy_number is None
                else strategy_number
            ),
            seed=seed,
            config=GameConfig.for_table_size(mode.initial_agent_count),
            table_mode_id=mode.mode_id,
            table_config_sha256=table_catalog.sha256,
            **kwargs,
        )

    @classmethod
    def from_agent_roster(
        cls,
        *,
        agent_catalog: AgentCatalog,
        roster_id: str,
        problem_bank: ProblemBank,
        agenda_catalog: AgendaCatalog,
        seed: int,
        strategy_number: int | None = None,
        **kwargs: Any,
    ) -> DealerGame:
        roster = agent_catalog.get_roster(roster_id)
        if agent_catalog.schema_version != agenda_catalog.schema_version:
            raise ValueError("agent and agenda schema versions must match")
        if "config" in kwargs or "player_ids" in kwargs:
            raise ValueError("agent rosters derive player IDs and GameConfig")
        config = GameConfig.for_table_size(roster.initial_agent_count)
        if agent_catalog.table_talk.max_chars != config.message_max_chars:
            raise ValueError("agent and dealer table-talk limits must match")
        return cls(
            player_ids=roster.player_ids(),
            problem_bank=problem_bank,
            agenda_catalog=agenda_catalog,
            strategy_number=(
                roster.recommended_agenda_strategy
                if strategy_number is None
                else strategy_number
            ),
            seed=seed,
            config=config,
            table_mode_id=f"agent_roster:{roster.roster_id}",
            agent_roster_id=roster.roster_id,
            agent_config_sha256=agent_catalog.sha256,
            agent_metadata=agent_catalog.roster_metadata(roster.roster_id),
            **kwargs,
        )

    def _require_phase(self, expected: Phase) -> None:
        if self.phase != expected:
            raise InvalidPhase(f"expected {expected.value}, current phase is {self.phase.value}")

    @property
    def current_round_number(self) -> int | None:
        return self._agenda_round.round_number if self._agenda_round else None

    @property
    def season_result(self) -> dict[str, Any] | None:
        return deepcopy(self._season_result)

    @property
    def public_history(self) -> list[dict[str, Any]]:
        return deepcopy(self._public_history)

    def _build_season_result(self, status: str) -> dict[str, Any]:
        positive = [
            player for player in self.players.values() if player.bankroll_cents > 0
        ]
        if status == "HOUSE_WIN":
            winner_ids: list[str] = []
        elif status == "SOLE_SURVIVOR":
            winner_ids = [positive[0].agent_id]
        else:
            high_score = max(player.bankroll_cents for player in self.players.values())
            winner_ids = [
                player.agent_id
                for player in self.players.values()
                if player.bankroll_cents == high_score
            ]
        return {
            "status": status,
            "winner_ids": winner_ids,
            "rounds_completed": self.rotation.consumed,
            "initial_agent_count": self.initial_agent_count,
            "rollover_cents": self.rollover_cents,
        }

    def reveal_category(self) -> dict[str, dict[str, Any]]:
        self._require_phase(Phase.CATEGORY_REVEAL)
        if self._season_result is not None:
            raise SeasonComplete("season is complete", self._season_result)
        if not any(player.bankroll_cents > 0 for player in self.players.values()):
            self._season_result = self._build_season_result("HOUSE_WIN")
            raise SeasonComplete("all players are inactive", self._season_result)
        try:
            self._agenda_round = self.rotation.next()
        except AgendaExhausted as exc:
            self._season_result = self._build_season_result("AGENDA_COMPLETE")
            raise SeasonComplete("agenda is complete", self._season_result) from exc
        self._problem = self.problem_bank.problems[self._agenda_round.problem_id]
        self._round_players = {
            player.agent_id: PlayerRound(
                agent_id=player.agent_id,
                bankroll_before_cents=player.bankroll_cents,
                bankroll_after_entry_cents=player.bankroll_cents,
            )
            for player in self.players.values()
            if player.bankroll_cents > 0
        }
        self._rollover_in_cents = self.rollover_cents
        self._pot_cents = self.rollover_cents
        self._entry_total_cents = 0
        self._winner_ids = []
        self._judge_results = {}
        self._public_problem_payloads = {}
        self.phase = Phase.ENTRY
        return {
            agent_id: {
                "round": self._agenda_round.round_number,
                "season_rounds": self.config.season_rounds,
                "category": self._agenda_round.category,
                "bankroll_cents": record.bankroll_before_cents,
                "entry_fee_cents": self.config.entry_fee_cents,
                "current_rollover_cents": self._rollover_in_cents,
                "initial_agent_count": self.initial_agent_count,
                "active_agent_count": len(self._round_players),
                "opponent_bankrolls_cents": {
                    opponent_id: opponent.bankroll_cents
                    for opponent_id, opponent in self.players.items()
                    if opponent_id != agent_id
                },
                "public_history": deepcopy(self._public_history),
            }
            for agent_id, record in self._round_players.items()
        }

    def collect_entries(self) -> None:
        self._require_phase(Phase.ENTRY)
        for agent_id, record in self._round_players.items():
            player = self.players[agent_id]
            if 0 < player.bankroll_cents < self.config.entry_fee_cents:
                stake = player.bankroll_cents
                record.show_hand = True
            else:
                stake = self.config.entry_fee_cents
            player.bankroll_cents -= stake
            if player.bankroll_cents < 0:
                raise AssertionError("entry produced a negative bankroll")
            record.entry_paid_cents = stake
            record.bankroll_after_entry_cents = player.bankroll_cents
            self._entry_total_cents += stake
            self._pot_cents += stake
        self._pot_cents += self.config.dealer_contribution_cents
        self.phase = Phase.TABLE_TALK

    def record_table_talk(self, messages: Mapping[str, str]) -> dict[str, str]:
        self._require_phase(Phase.TABLE_TALK)
        unknown = set(messages) - set(self._round_players)
        if unknown:
            raise ValueError(f"messages supplied for nonparticipants: {sorted(unknown)}")
        display_messages: dict[str, str] = {}
        for agent_id, record in self._round_players.items():
            message = messages.get(agent_id, "")
            if not isinstance(message, str):
                raise TypeError(f"table talk from {agent_id} must be a string")
            if len(message) > self.config.message_max_chars:
                raise ValueError(
                    f"table talk from {agent_id} exceeds {self.config.message_max_chars} characters"
                )
            record.public_message = message
            record.public_message_display = html.escape(message, quote=True)
            display_messages[agent_id] = record.public_message_display
        self.phase = Phase.PROBLEM_REVEAL
        return display_messages

    def reveal_problem(self) -> dict[str, dict[str, Any]]:
        self._require_phase(Phase.PROBLEM_REVEAL)
        assert self._problem is not None and self._agenda_round is not None
        shared_messages = {
            agent_id: record.public_message for agent_id, record in self._round_players.items()
        }
        problem_fields = public_problem(self._problem)
        payloads: dict[str, dict[str, Any]] = {}
        for agent_id, record in self._round_players.items():
            payloads[agent_id] = {
                **problem_fields,
                "pot_cents": self._pot_cents,
                "bankroll_after_entry_cents": record.bankroll_after_entry_cents,
                "round": self._agenda_round.round_number,
                "season_rounds": self.config.season_rounds,
                "reasoning_menu_cents": {
                    tier.value: self.config.reasoning_prices_cents[tier] for tier in TIER_ORDER
                },
                "public_messages": shared_messages,
                "initial_agent_count": self.initial_agent_count,
                "active_agent_count": len(self._round_players),
                "opponent_bankrolls_cents": {
                    opponent_id: opponent.bankroll_cents
                    for opponent_id, opponent in self.players.items()
                    if opponent_id != agent_id
                },
                "public_history": deepcopy(self._public_history),
            }
        self._public_problem_payloads = deepcopy(payloads)
        self.phase = Phase.ROUTING
        return deepcopy(payloads)

    @staticmethod
    def _returned_tier(response: Any) -> ReasoningTier | None:
        if not isinstance(response, Mapping):
            return None
        raw = response.get("reasoning_tier")
        try:
            return ReasoningTier(raw)
        except (ValueError, TypeError):
            return None

    def route_and_purchase(
        self,
        routers: Mapping[str, Router],
    ) -> None:
        self._require_phase(Phase.ROUTING)
        if set(routers) != set(self._round_players):
            raise ValueError("routers must be supplied for exactly the participating players")
        for agent_id, record in self._round_players.items():
            player = self.players[agent_id]
            if record.show_hand:
                record.router_tier = ReasoningTier.NONE.value
                record.reasoning_price_cents = 0
                continue

            affordable = affordable_tiers(player.bankroll_cents, self.config)
            base_payload = deepcopy(self._public_problem_payloads[agent_id])
            base_payload["affordable_tiers"] = [tier.value for tier in affordable]
            responses: list[Any] = []
            selected: ReasoningTier | None = None
            for attempt in range(2):
                request = deepcopy(base_payload)
                request["router_retry"] = attempt == 1
                response = routers[agent_id](request)
                responses.append(response)
                record.router_attempts += 1
                candidate = self._returned_tier(response)
                if candidate in affordable:
                    selected = candidate
                    break

            if selected is None:
                record.router_fallback = True
                attempted_tiers = [self._returned_tier(response) for response in responses]
                overspend = any(
                    tier is not None and self.config.reasoning_prices_cents[tier] > player.bankroll_cents
                    for tier in attempted_tiers
                )
                if overspend:
                    selected = highest_affordable_tier(player.bankroll_cents, self.config)
                elif ReasoningTier.NONE in affordable:
                    selected = ReasoningTier.NONE

            # An exact-entry bankroll can legally enter under the frozen V1 rule
            # but has $0 left for the priced `none` tier. Preserve no-negative
            # accounting by forcing the base solver at zero additional cost.
            if selected is None:
                selected = ReasoningTier.NONE
                price = 0
                record.router_fallback = True
            else:
                price = self.config.reasoning_prices_cents[selected]
            if price > player.bankroll_cents:
                raise AssertionError("router resolution selected an unaffordable tier")
            player.bankroll_cents -= price
            record.router_tier = selected.value
            record.reasoning_price_cents = price
        self.phase = Phase.SOLVING

    def solve(
        self,
        solvers: Mapping[str, Solver],
    ) -> None:
        self._require_phase(Phase.SOLVING)
        if set(solvers) != set(self._round_players):
            raise ValueError("solvers must be supplied for exactly the participating players")
        for agent_id, record in self._round_players.items():
            payload = deepcopy(self._public_problem_payloads[agent_id])
            payload["reasoning_tier"] = record.router_tier
            payload["reasoning_config"] = reasoning_config(record.router_tier or ReasoningTier.NONE)
            response = solvers[agent_id](payload)
            if not isinstance(response, Mapping) or not isinstance(response.get("answer"), str):
                raise ValueError(f"solver {agent_id} must return a string answer field")
            record.submitted_answer = response["answer"]
            record.telemetry = {
                key: response[key]
                for key in (
                    "actual_input_tokens",
                    "actual_output_tokens",
                    "actual_reasoning_tokens",
                    "latency_ms",
                    "model",
                    "api_reasoning_configuration",
                )
                if key in response
            }
        self.phase = Phase.JUDGING

    def judge(self) -> dict[str, dict[str, Any]]:
        self._require_phase(Phase.JUDGING)
        assert self._problem is not None
        results: dict[str, dict[str, Any]] = {}
        for agent_id, record in self._round_players.items():
            result = judge_answer(self._problem, record.submitted_answer or "")
            record.correct = result.correct
            results[agent_id] = result.as_dict()
        self._judge_results = results
        self.phase = Phase.PAYOUT
        return results

    def payout(self) -> dict[str, int]:
        self._require_phase(Phase.PAYOUT)
        self._winner_ids = [
            agent_id for agent_id, record in self._round_players.items() if record.correct
        ]
        share, remainder = split_pot(self._pot_cents, len(self._winner_ids))
        for winner_id in self._winner_ids:
            self.players[winner_id].bankroll_cents += share
            self._round_players[winner_id].prize_received_cents = share
        self.rollover_cents = remainder
        if self._winner_ids:
            self.rollover_chain = 0 if remainder == 0 else self.rollover_chain + 1
        else:
            self.rollover_chain += 1
        for agent_id, record in self._round_players.items():
            record.bankroll_after_round_cents = self.players[agent_id].bankroll_cents
        positive_count = sum(
            player.bankroll_cents > 0 for player in self.players.values()
        )
        if self.initial_agent_count >= 2 and positive_count == 0:
            self._season_result = self._build_season_result("HOUSE_WIN")
        elif self.initial_agent_count >= 2 and positive_count == 1:
            self._season_result = self._build_season_result("SOLE_SURVIVOR")
        elif self.rotation.remaining == 0:
            self._season_result = self._build_season_result("AGENDA_COMPLETE")
        self.phase = Phase.ROUND_COMPLETE
        return {winner_id: share for winner_id in self._winner_ids}

    def complete_round(self) -> dict[str, Any]:
        self._require_phase(Phase.ROUND_COMPLETE)
        assert self._agenda_round is not None and self._problem is not None
        event = {
            "schema_version": "1.0",
            "currency_unit": "cents",
            "season_id": self.season_id,
            "round": self._agenda_round.round_number,
            "strategy_number": self.agenda.strategy_number,
            "table_mode_id": self.table_mode_id,
            "initial_agent_count": self.initial_agent_count,
            "table_config_sha256": self.table_config_sha256,
            "agent_roster_id": self.agent_roster_id,
            "agent_config_sha256": self.agent_config_sha256,
            "problem_id": self._agenda_round.problem_id,
            "category": self._agenda_round.category,
            "hidden_difficulty": self._agenda_round.dealer_difficulty,
            "hidden_guessability": self._agenda_round.guessability,
            "hidden_reference_reasoning_tier": (
                self._agenda_round.reference_reasoning_tier.value
                if self._agenda_round.reference_reasoning_tier is not None
                else None
            ),
            "hidden_round_role": self._agenda_round.round_role,
            "correct_answer": self._problem["answer"]["display"],
            "rollover_in_cents": self._rollover_in_cents,
            "entry_total_cents": self._entry_total_cents,
            "dealer_contribution_cents": self.config.dealer_contribution_cents,
            "pot_cents": self._pot_cents,
            "winner_ids": self._winner_ids,
            "rollover_out_cents": self.rollover_cents,
            "problem_bank_sha256": self.problem_bank.sha256,
            "agenda_sha256": self.agenda_catalog.sha256,
            "model_identifier": self.model_identifier,
            "reasoning_mapping_version": REASONING_MAPPING_VERSION,
            "run_seed": self.seed,
            "code_version": self.code_version,
            "max_rollover_chain": self.config.max_rollover_chain,
            "season_result": deepcopy(self._season_result),
            "table_talk": [
                {
                    "agent_id": record.agent_id,
                    "message": record.public_message,
                }
                for record in self._round_players.values()
            ],
            "agents": [
                {
                    "agent_id": record.agent_id,
                    "bankroll_before_cents": record.bankroll_before_cents,
                    "entry_paid_cents": record.entry_paid_cents,
                    "show_hand": record.show_hand,
                    "public_message": record.public_message,
                    "public_message_display": record.public_message_display,
                    "bankroll_after_entry_cents": record.bankroll_after_entry_cents,
                    "router_tier": record.router_tier,
                    "reasoning_price_cents": record.reasoning_price_cents,
                    "router_fallback": record.router_fallback,
                    "router_attempts": record.router_attempts,
                    "submitted_answer": record.submitted_answer,
                    "correct": record.correct,
                    "judge": self._judge_results[record.agent_id],
                    "prize_received_cents": record.prize_received_cents,
                    "bankroll_after_round_cents": record.bankroll_after_round_cents,
                    **self.agent_metadata.get(record.agent_id, {}),
                    **record.telemetry,
                }
                for record in self._round_players.values()
            ],
        }
        if self._event_log:
            self._event_log.append(event)
        self._public_history.append(
            {
                "round": event["round"],
                "category": event["category"],
                "table_talk": deepcopy(event["table_talk"]),
                "agents": [
                    {
                        "agent_id": record.agent_id,
                        "reasoning_tier": record.router_tier,
                        "submitted_answer": record.submitted_answer,
                        "correct": record.correct,
                        "prize_received_cents": record.prize_received_cents,
                        "bankroll_after_round_cents": record.bankroll_after_round_cents,
                    }
                    for record in self._round_players.values()
                ],
            }
        )
        self._last_event = event
        self._agenda_round = None
        self._problem = None
        self._round_players = {}
        self._public_problem_payloads = {}
        self.phase = Phase.CATEGORY_REVEAL
        return event


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Pay-to-Think dealer inputs")
    parser.add_argument("--bank", required=True, type=Path)
    parser.add_argument("--agendas", required=True, type=Path)
    parser.add_argument("--strategy", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--tables", type=Path)
    parser.add_argument("--table")
    parser.add_argument("--agents", type=Path)
    parser.add_argument("--roster")
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    bank = load_problem_bank(args.bank)
    catalog = load_agendas(args.agendas, bank)
    if args.strategy not in catalog.agendas:
        raise SystemExit(f"unknown strategy {args.strategy}")
    if bool(args.tables) != bool(args.table):
        raise SystemExit("--tables and --table must be supplied together")
    if bool(args.agents) != bool(args.roster):
        raise SystemExit("--agents and --roster must be supplied together")
    table_summary: dict[str, Any] = {}
    if args.tables:
        tables = load_table_modes(args.tables, catalog)
        try:
            mode = tables.get(args.table)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        table_config = GameConfig.for_table_size(mode.initial_agent_count)
        table_summary = {
            "table_mode_id": mode.mode_id,
            "initial_agent_count": mode.initial_agent_count,
            "dealer_contribution_cents": table_config.dealer_contribution_cents,
            "normal_pot_cents": (
                mode.initial_agent_count * table_config.entry_fee_cents
                + table_config.dealer_contribution_cents
            ),
            "recommended_agenda_strategy": mode.recommended_agenda_strategy,
            "table_config_sha256": tables.sha256,
        }
    agent_summary: dict[str, Any] = {}
    if args.agents:
        agents = load_agent_catalog(args.agents)
        try:
            roster = agents.get_roster(args.roster)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if table_summary and roster.initial_agent_count != table_summary["initial_agent_count"]:
            raise SystemExit("selected table mode and agent roster have different seat counts")
        roster_config = GameConfig.for_table_size(roster.initial_agent_count)
        agent_summary = {
            "agent_roster_id": roster.roster_id,
            "initial_agent_count": roster.initial_agent_count,
            "dealer_contribution_cents": roster_config.dealer_contribution_cents,
            "normal_pot_cents": (
                roster.initial_agent_count * roster_config.entry_fee_cents
                + roster_config.dealer_contribution_cents
            ),
            "recommended_agenda_strategy": roster.recommended_agenda_strategy,
            "agent_config_sha256": agents.sha256,
            "llm_agent_count": sum(
                agents.profiles[seat.profile_id].runtime_kind.value == "llm"
                for seat in roster.seats
            ),
        }
    if not args.validate_only:
        raise SystemExit("provider execution is injected through DealerGame; pass --validate-only")
    agenda = catalog.agendas[args.strategy]
    print(
        json.dumps(
            {
                "valid": True,
                "strategy_number": agenda.strategy_number,
                "agenda_name": agenda.name,
                "round_count": len(agenda.rounds),
                "problem_count": len(bank.problems),
                "problem_bank_sha256": bank.sha256,
                "agenda_sha256": catalog.sha256,
                "run_seed": args.seed,
                **table_summary,
                **agent_summary,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
