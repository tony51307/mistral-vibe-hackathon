from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .models import (
    Agenda,
    AgendaCatalog,
    AgendaRound,
    ProblemBank,
    ReasoningTier,
    TableCatalog,
    TableMode,
)


class DataValidationError(ValueError):
    pass


SUPPORTED_VALIDATORS = {"integer", "numeric", "boolean", "normalized_text"}
SUPPORTED_NORMALIZATIONS = {
    "trim",
    "unicode_nfkc",
    "casefold",
    "remove_math_delimiters",
    "collapse_whitespace",
}


def _read_bytes(path: str | Path) -> tuple[Path, bytes]:
    resolved = Path(path).resolve()
    try:
        return resolved, resolved.read_bytes()
    except OSError as exc:
        raise DataValidationError(f"cannot read {resolved}: {exc}") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DataValidationError(f"{context} must be an object")
    return value


def _require_nonempty_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(f"{context} must be a non-empty string")
    return value


def _validate_validator(problem_id: str, validator: Any) -> None:
    item = _require_mapping(validator, f"{problem_id}.answer.validator")
    kind = item.get("kind")
    if kind not in SUPPORTED_VALIDATORS:
        raise DataValidationError(f"{problem_id}: unsupported validator kind {kind!r}")
    if kind == "integer":
        if isinstance(item.get("value"), bool) or not isinstance(item.get("value"), int):
            raise DataValidationError(f"{problem_id}: integer validator needs an integer value")
    elif kind == "numeric":
        value = item.get("value")
        tolerance = item.get("abs_tolerance")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DataValidationError(f"{problem_id}: numeric validator needs a numeric value")
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance < 0:
            raise DataValidationError(f"{problem_id}: numeric validator needs a nonnegative abs_tolerance")
    elif kind == "boolean":
        if not isinstance(item.get("value"), bool):
            raise DataValidationError(f"{problem_id}: boolean validator needs a boolean value")
        aliases = item.get("accepted_text")
        if not isinstance(aliases, list) or not aliases or not all(isinstance(x, str) for x in aliases):
            raise DataValidationError(f"{problem_id}: boolean validator needs accepted_text")
    else:
        accepted = item.get("accepted")
        operations = item.get("normalization")
        if not isinstance(accepted, list) or not accepted or not all(isinstance(x, str) for x in accepted):
            raise DataValidationError(f"{problem_id}: normalized_text validator needs accepted strings")
        if not isinstance(operations, list) or not all(op in SUPPORTED_NORMALIZATIONS for op in operations):
            raise DataValidationError(f"{problem_id}: invalid normalization operations")


def load_problem_bank(path: str | Path) -> ProblemBank:
    resolved, data = _read_bytes(path)
    try:
        document = _require_mapping(json.loads(data), "problem bank")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataValidationError(f"invalid problem-bank JSON: {exc}") from exc

    schema_version = _require_nonempty_string(document.get("schema_version"), "schema_version")
    name = _require_nonempty_string(document.get("name"), "name")
    raw_problems = document.get("problems")
    if not isinstance(raw_problems, list) or not raw_problems:
        raise DataValidationError("problems must be a non-empty list")

    problems: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_problems):
        problem = _require_mapping(raw, f"problems[{index}]")
        problem_id = _require_nonempty_string(problem.get("id"), f"problems[{index}].id")
        if problem_id in problems:
            raise DataValidationError(f"duplicate problem id: {problem_id}")
        _require_nonempty_string(problem.get("category"), f"{problem_id}.category")
        _require_nonempty_string(problem.get("prompt_markdown"), f"{problem_id}.prompt_markdown")
        answer = _require_mapping(problem.get("answer"), f"{problem_id}.answer")
        _validate_validator(problem_id, answer.get("validator"))
        dealer_meta = _require_mapping(problem.get("dealer_meta"), f"{problem_id}.dealer_meta")
        _require_nonempty_string(dealer_meta.get("difficulty"), f"{problem_id}.dealer_meta.difficulty")
        _require_nonempty_string(dealer_meta.get("guessability"), f"{problem_id}.dealer_meta.guessability")
        problems[problem_id] = problem

    return ProblemBank(schema_version, name, problems, _sha256(data), resolved)


def load_agendas(path: str | Path, bank: ProblemBank) -> AgendaCatalog:
    resolved, data = _read_bytes(path)
    try:
        document = _require_mapping(yaml.safe_load(data), "agenda document")
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise DataValidationError(f"invalid agenda YAML: {exc}") from exc

    schema_version = _require_nonempty_string(document.get("schema_version"), "schema_version")
    if schema_version != bank.schema_version:
        raise DataValidationError(
            f"agenda schema {schema_version!r} does not match problem-bank schema {bank.schema_version!r}"
        )
    declared_bank = _require_nonempty_string(document.get("problem_bank"), "problem_bank")
    if declared_bank != bank.path.name:
        raise DataValidationError(
            f"agenda expects problem bank {declared_bank!r}, loaded {bank.path.name!r}"
        )
    raw_agendas = document.get("agendas")
    if not isinstance(raw_agendas, list) or not raw_agendas:
        raise DataValidationError("agendas must be a non-empty list")

    agendas: dict[int, Agenda] = {}
    for raw_agenda in raw_agendas:
        item = _require_mapping(raw_agenda, "agenda")
        strategy = item.get("strategy_number")
        if isinstance(strategy, bool) or not isinstance(strategy, int) or strategy <= 0:
            raise DataValidationError("strategy_number must be a positive integer")
        if strategy in agendas:
            raise DataValidationError(f"duplicate strategy_number: {strategy}")
        name = _require_nonempty_string(item.get("name"), f"agenda {strategy}.name")
        objective = _require_nonempty_string(item.get("objective"), f"agenda {strategy}.objective")
        raw_rounds = item.get("rounds")
        round_count = item.get("round_count")
        if not isinstance(raw_rounds, list) or round_count != len(raw_rounds) or round_count <= 0:
            raise DataValidationError(f"agenda {strategy}: round_count does not match rounds")
        rounds: list[AgendaRound] = []
        for expected_round, raw_round in enumerate(raw_rounds, start=1):
            round_item = _require_mapping(raw_round, f"agenda {strategy} round {expected_round}")
            if round_item.get("round") != expected_round:
                raise DataValidationError(f"agenda {strategy}: rounds must be consecutive from 1")
            problem_id = _require_nonempty_string(round_item.get("problem_id"), "problem_id")
            if problem_id not in bank.problems:
                raise DataValidationError(f"agenda {strategy}: unknown problem_id {problem_id!r}")
            problem = bank.problems[problem_id]
            category = _require_nonempty_string(round_item.get("category"), "category")
            difficulty = _require_nonempty_string(round_item.get("dealer_difficulty"), "dealer_difficulty")
            guessability = _require_nonempty_string(round_item.get("guessability"), "guessability")
            canonical_meta = problem["dealer_meta"]
            if category != problem["category"]:
                raise DataValidationError(f"agenda {strategy}: category mismatch for {problem_id}")
            if difficulty != canonical_meta["difficulty"]:
                raise DataValidationError(f"agenda {strategy}: difficulty mismatch for {problem_id}")
            if guessability != canonical_meta["guessability"]:
                raise DataValidationError(f"agenda {strategy}: guessability mismatch for {problem_id}")
            rounds.append(AgendaRound(expected_round, problem_id, category, difficulty, guessability))
        agendas[strategy] = Agenda(strategy, name, objective, tuple(rounds))

    return AgendaCatalog(schema_version, agendas, _sha256(data), resolved)


def load_table_modes(
    path: str | Path,
    agenda_catalog: AgendaCatalog | None = None,
) -> TableCatalog:
    resolved, data = _read_bytes(path)
    try:
        document = _require_mapping(yaml.safe_load(data), "table-mode document")
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise DataValidationError(f"invalid table-mode YAML: {exc}") from exc

    schema_version = _require_nonempty_string(document.get("schema_version"), "schema_version")
    if agenda_catalog and schema_version != agenda_catalog.schema_version:
        raise DataValidationError(
            f"table schema {schema_version!r} does not match agenda schema "
            f"{agenda_catalog.schema_version!r}"
        )

    economy = _require_mapping(document.get("economy"), "economy")
    expected_economy = {
        "minimum_agents": 2,
        "maximum_agents": 10,
        "starting_bankroll_cents": 8_000,
        "entry_fee_cents": 1_000,
        "dealer_contribution_per_initial_agent_cents": 300,
        "season_rounds": 25,
        "max_rollover_chain": 3,
        "reasoning_prices_cents": {
            tier.value: price
            for tier, price in {
                ReasoningTier.NONE: 100,
                ReasoningTier.LOW: 200,
                ReasoningTier.MEDIUM: 300,
                ReasoningTier.HIGH: 500,
                ReasoningTier.XHIGH: 900,
            }.items()
        },
    }
    if economy != expected_economy:
        raise DataValidationError("table economy must match the frozen V1 scaling contract")

    default_mode = _require_nonempty_string(document.get("default_mode"), "default_mode")
    raw_modes = document.get("table_modes")
    if not isinstance(raw_modes, list) or not raw_modes:
        raise DataValidationError("table_modes must be a non-empty list")

    modes: dict[str, TableMode] = {}
    for index, raw_mode in enumerate(raw_modes):
        item = _require_mapping(raw_mode, f"table_modes[{index}]")
        mode_id = _require_nonempty_string(item.get("id"), f"table_modes[{index}].id")
        if mode_id in modes:
            raise DataValidationError(f"duplicate table mode id: {mode_id}")
        name = _require_nonempty_string(item.get("name"), f"table mode {mode_id}.name")
        count = item.get("initial_agent_count")
        if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= 10:
            raise DataValidationError(
                f"table mode {mode_id}: initial_agent_count must be between 2 and 10"
            )
        strategy = item.get("recommended_agenda_strategy")
        if isinstance(strategy, bool) or not isinstance(strategy, int) or strategy <= 0:
            raise DataValidationError(
                f"table mode {mode_id}: recommended_agenda_strategy must be positive"
            )
        if agenda_catalog and strategy not in agenda_catalog.agendas:
            raise DataValidationError(
                f"table mode {mode_id}: unknown agenda strategy {strategy}"
            )
        use_cases = item.get("use_cases")
        if not isinstance(use_cases, list) or not use_cases or not all(
            isinstance(value, str) and value.strip() for value in use_cases
        ):
            raise DataValidationError(f"table mode {mode_id}: use_cases must be strings")
        modes[mode_id] = TableMode(mode_id, name, count, strategy, tuple(use_cases))

    if default_mode not in modes:
        raise DataValidationError(f"default_mode {default_mode!r} is not defined")
    return TableCatalog(schema_version, default_mode, modes, _sha256(data), resolved)


def public_problem(problem: dict[str, Any]) -> dict[str, str]:
    """Return the only canonical problem fields that may cross the dealer boundary."""
    return {
        "problem_id": problem["id"],
        "category": problem["category"],
        "prompt_markdown": problem["prompt_markdown"],
    }
