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
SUPPORTED_PROBLEM_BANK_SCHEMAS = {"1.0", "2.0"}
SUPPORTED_AGENDA_SCHEMAS = {"1.0", "3.0"}
SUPPORTED_TABLE_SCHEMAS = {"1.0"}
SUPPORTED_DIFFICULTIES = {"trivial", "easy", "medium", "hard", "very_hard"}
SUPPORTED_GUESSABILITY = {"low", "medium", "high"}
SUPPORTED_REASONING_PROFILES = {
    "cheap_capture",
    "cheap_or_low",
    "knowledge_or_high",
    "legacy",
    "reasoning_sensitive_low",
    "reasoning_sensitive_medium",
    "reasoning_sensitive_high",
}
SUPPORTED_NORMALIZATIONS = {
    "trim",
    "unicode_nfkc",
    "casefold",
    "remove_math_delimiters",
    "collapse_whitespace",
}
SUPPORTED_ROUND_ROLES = {
    "cheap_capture",
    "decision_boundary",
    "guessability_trap",
    "reasoning_payoff",
}


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DataValidationError(
                f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}"
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _read_bytes(path: str | Path) -> tuple[Path, bytes]:
    resolved = Path(path).resolve()
    try:
        return resolved, resolved.read_bytes()
    except OSError as exc:
        raise DataValidationError(f"cannot read {resolved}: {exc}") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _combined_sha256(source_sha256s: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name, source_digest in sorted(source_sha256s.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source_digest.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _strict_json_loads(data: bytes) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DataValidationError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    return json.loads(data, object_pairs_hook=unique_object)


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
        allow_fraction = item.get("allow_fraction")
        if allow_fraction is not None and not isinstance(allow_fraction, bool):
            raise DataValidationError(f"{problem_id}: allow_fraction must be boolean")
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
        document = _require_mapping(_strict_json_loads(data), "problem bank")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataValidationError(f"invalid problem-bank JSON: {exc}") from exc

    schema_version = _require_nonempty_string(document.get("schema_version"), "schema_version")
    if schema_version not in SUPPORTED_PROBLEM_BANK_SCHEMAS:
        raise DataValidationError(f"unsupported problem-bank schema {schema_version!r}")
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
        category = _require_nonempty_string(problem.get("category"), f"{problem_id}.category")
        subcategory = problem.get("subcategory")
        if subcategory is not None:
            _require_nonempty_string(subcategory, f"{problem_id}.subcategory")
        _require_nonempty_string(problem.get("prompt_markdown"), f"{problem_id}.prompt_markdown")
        answer = _require_mapping(problem.get("answer"), f"{problem_id}.answer")
        _require_nonempty_string(answer.get("display"), f"{problem_id}.answer.display")
        _validate_validator(problem_id, answer.get("validator"))
        dealer_meta = _require_mapping(problem.get("dealer_meta"), f"{problem_id}.dealer_meta")
        difficulty = _require_nonempty_string(
            dealer_meta.get("difficulty"), f"{problem_id}.dealer_meta.difficulty"
        )
        if difficulty not in SUPPORTED_DIFFICULTIES:
            raise DataValidationError(f"{problem_id}: invalid difficulty {difficulty!r}")
        guessability = _require_nonempty_string(
            dealer_meta.get("guessability"), f"{problem_id}.dealer_meta.guessability"
        )
        if guessability not in SUPPORTED_GUESSABILITY:
            raise DataValidationError(f"{problem_id}: invalid guessability {guessability!r}")
        if schema_version == "2.0":
            if category not in {
                "algorithms",
                "computer_science",
                "general_quantitative_reasoning",
                "logic",
                "math",
                "physics",
                "probability",
            }:
                raise DataValidationError(f"{problem_id}: invalid V2 category {category!r}")
            profile = _require_nonempty_string(
                dealer_meta.get("reasoning_profile"),
                f"{problem_id}.dealer_meta.reasoning_profile",
            )
            if profile not in SUPPORTED_REASONING_PROFILES - {"legacy"}:
                raise DataValidationError(f"{problem_id}: invalid reasoning_profile {profile!r}")
            raw_tier = _require_nonempty_string(
                dealer_meta.get("suggested_reasoning_tier"),
                f"{problem_id}.dealer_meta.suggested_reasoning_tier",
            )
            try:
                ReasoningTier(raw_tier)
            except ValueError as exc:
                raise DataValidationError(
                    f"{problem_id}: invalid suggested_reasoning_tier {raw_tier!r}"
                ) from exc
            tags = dealer_meta.get("tags")
            if not isinstance(tags, list) or not tags or not all(
                isinstance(value, str) and value.strip() for value in tags
            ):
                raise DataValidationError(f"{problem_id}: tags must be non-empty strings")
        problems[problem_id] = problem

    source_sha256 = _sha256(data)
    source_name = resolved.name
    return ProblemBank(
        schema_version,
        name,
        problems,
        source_sha256,
        resolved,
        (resolved,),
        {source_name: source_sha256},
        {source_name: schema_version},
        {problem_id: source_name for problem_id in problems},
    )


def load_problem_banks(paths: list[str | Path] | tuple[str | Path, ...]) -> ProblemBank:
    if not paths:
        raise DataValidationError("at least one problem bank is required")
    sources = [load_problem_bank(path) for path in paths]
    source_names = [source.path.name for source in sources]
    if len(set(source_names)) != len(source_names):
        raise DataValidationError("problem-bank filenames must be unique")
    if len(sources) == 1:
        return sources[0]

    problems: dict[str, dict[str, Any]] = {}
    source_by_problem_id: dict[str, str] = {}
    for source in sources:
        for problem_id, problem in source.problems.items():
            if problem_id in problems:
                raise DataValidationError(f"duplicate problem id across banks: {problem_id}")
            problems[problem_id] = problem
            source_by_problem_id[problem_id] = source.path.name

    ordered_sources = tuple(sorted((source.path for source in sources), key=lambda path: path.name))
    sources_by_name = {source.path.name: source for source in sources}
    source_sha256s = {
        name: sources_by_name[name].sha256 for name in sorted(sources_by_name)
    }
    source_schema_versions = {
        name: sources_by_name[name].schema_version for name in sorted(sources_by_name)
    }
    return ProblemBank(
        "+".join(sorted(source.schema_version for source in sources)),
        "+".join(sources_by_name[name].name for name in sorted(sources_by_name)),
        problems,
        _combined_sha256(source_sha256s),
        ordered_sources[0],
        ordered_sources,
        source_sha256s,
        source_schema_versions,
        source_by_problem_id,
    )


def load_agendas(path: str | Path, bank: ProblemBank) -> AgendaCatalog:
    resolved, data = _read_bytes(path)
    try:
        document = _require_mapping(
            yaml.load(data, Loader=_UniqueKeyLoader),
            "agenda document",
        )
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise DataValidationError(f"invalid agenda YAML: {exc}") from exc

    schema_version = _require_nonempty_string(document.get("schema_version"), "schema_version")
    if schema_version not in SUPPORTED_AGENDA_SCHEMAS:
        raise DataValidationError(f"unsupported agenda schema {schema_version!r}")
    loaded_source_names = set(bank.source_sha256s) or {bank.path.name}
    source_labels_by_file: dict[str, str] = {}
    if schema_version == "1.0":
        declared_bank = _require_nonempty_string(document.get("problem_bank"), "problem_bank")
        if declared_bank not in loaded_source_names:
            raise DataValidationError(
                f"agenda expects problem bank {declared_bank!r}, loaded {sorted(loaded_source_names)!r}"
            )
    else:
        raw_declared_banks = _require_mapping(document.get("problem_banks"), "problem_banks")
        for label, filename in raw_declared_banks.items():
            source_label = _require_nonempty_string(label, "problem_banks label")
            source_filename = _require_nonempty_string(
                filename, f"problem_banks.{source_label}"
            )
            if source_filename in source_labels_by_file:
                raise DataValidationError(
                    f"agenda declares problem bank {source_filename!r} more than once"
                )
            source_labels_by_file[source_filename] = source_label
        missing_banks = set(source_labels_by_file) - loaded_source_names
        if missing_banks:
            raise DataValidationError(
                f"agenda problem banks are not loaded: {sorted(missing_banks)!r}"
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
        showcase_bias = item.get("showcase_bias", False)
        if not isinstance(showcase_bias, bool):
            raise DataValidationError(f"agenda {strategy}: showcase_bias must be boolean")
        dynamic_advantage = item.get("dynamic_advantage", [])
        if not isinstance(dynamic_advantage, list) or not all(
            isinstance(value, str) and value.strip() for value in dynamic_advantage
        ):
            raise DataValidationError(
                f"agenda {strategy}: dynamic_advantage must be a list of strings"
            )
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
            source_bank = round_item.get("source_bank")
            if schema_version == "3.0":
                source_bank = _require_nonempty_string(source_bank, "source_bank")
                actual_source_file = bank.source_by_problem_id[problem_id]
                expected_source_bank = source_labels_by_file.get(actual_source_file)
                if source_bank != expected_source_bank:
                    raise DataValidationError(
                        f"agenda {strategy}: source_bank mismatch for {problem_id}; "
                        f"expected {expected_source_bank!r}"
                    )
            elif source_bank is not None:
                source_bank = _require_nonempty_string(source_bank, "source_bank")
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
            raw_tier = round_item.get("reference_reasoning_tier")
            try:
                reference_tier = ReasoningTier(raw_tier) if raw_tier is not None else None
            except ValueError as exc:
                raise DataValidationError(
                    f"agenda {strategy}: invalid reference_reasoning_tier {raw_tier!r}"
                ) from exc
            canonical_tier = canonical_meta.get("suggested_reasoning_tier")
            if schema_version == "3.0" and canonical_tier is not None and (
                reference_tier is None or reference_tier.value != canonical_tier
            ):
                raise DataValidationError(
                    f"agenda {strategy}: reference reasoning tier mismatch for {problem_id}"
                )
            round_role = round_item.get("round_role")
            if round_role is not None and round_role not in SUPPORTED_ROUND_ROLES:
                raise DataValidationError(
                    f"agenda {strategy}: invalid round_role {round_role!r}"
                )
            reasoning_profile = round_item.get("reasoning_profile")
            if schema_version == "3.0":
                reasoning_profile = _require_nonempty_string(
                    reasoning_profile, "reasoning_profile"
                )
            elif reasoning_profile is not None:
                reasoning_profile = _require_nonempty_string(
                    reasoning_profile, "reasoning_profile"
                )
            if reasoning_profile is not None:
                if reasoning_profile not in SUPPORTED_REASONING_PROFILES:
                    raise DataValidationError(
                        f"agenda {strategy}: invalid reasoning_profile {reasoning_profile!r}"
                    )
                canonical_profile = canonical_meta.get("reasoning_profile", "legacy")
                if reasoning_profile != canonical_profile:
                    raise DataValidationError(
                        f"agenda {strategy}: reasoning profile mismatch for {problem_id}"
                    )
            rounds.append(
                AgendaRound(
                    expected_round,
                    problem_id,
                    category,
                    difficulty,
                    guessability,
                    reference_tier,
                    round_role,
                    source_bank,
                    reasoning_profile,
                )
            )
        agendas[strategy] = Agenda(
            strategy,
            name,
            objective,
            tuple(rounds),
            showcase_bias,
            tuple(dynamic_advantage),
        )

    source_sha256 = _sha256(data)
    return AgendaCatalog(
        schema_version,
        agendas,
        source_sha256,
        resolved,
        (resolved,),
        {resolved.name: source_sha256},
        {resolved.name: schema_version},
    )


def load_agenda_catalogs(
    paths: list[str | Path] | tuple[str | Path, ...],
    bank: ProblemBank,
) -> AgendaCatalog:
    if not paths:
        raise DataValidationError("at least one agenda catalog is required")
    catalogs = [load_agendas(path, bank) for path in paths]
    source_names = [catalog.path.name for catalog in catalogs]
    if len(set(source_names)) != len(source_names):
        raise DataValidationError("agenda-catalog filenames must be unique")
    if len(catalogs) == 1:
        return catalogs[0]

    agendas: dict[int, Agenda] = {}
    for catalog in catalogs:
        for strategy, agenda in catalog.agendas.items():
            if strategy in agendas:
                raise DataValidationError(
                    f"duplicate strategy_number across agenda catalogs: {strategy}"
                )
            agendas[strategy] = agenda

    ordered_sources = tuple(
        sorted((catalog.path for catalog in catalogs), key=lambda path: path.name)
    )
    catalogs_by_name = {catalog.path.name: catalog for catalog in catalogs}
    source_sha256s = {
        name: catalogs_by_name[name].sha256 for name in sorted(catalogs_by_name)
    }
    source_schema_versions = {
        name: catalogs_by_name[name].schema_version for name in sorted(catalogs_by_name)
    }
    return AgendaCatalog(
        "+".join(sorted(catalog.schema_version for catalog in catalogs)),
        agendas,
        _combined_sha256(source_sha256s),
        ordered_sources[0],
        ordered_sources,
        source_sha256s,
        source_schema_versions,
    )


def load_table_modes(
    path: str | Path,
    agenda_catalog: AgendaCatalog | None = None,
) -> TableCatalog:
    resolved, data = _read_bytes(path)
    try:
        document = _require_mapping(
            yaml.load(data, Loader=_UniqueKeyLoader),
            "table-mode document",
        )
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise DataValidationError(f"invalid table-mode YAML: {exc}") from exc

    schema_version = _require_nonempty_string(document.get("schema_version"), "schema_version")
    if schema_version not in SUPPORTED_TABLE_SCHEMAS:
        raise DataValidationError(f"unsupported table schema {schema_version!r}")

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
