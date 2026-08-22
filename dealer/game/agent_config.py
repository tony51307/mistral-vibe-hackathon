from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from enum import Enum
import hashlib
import os
from pathlib import Path
import re
from typing import Any, Mapping

import yaml


class AgentConfigError(ValueError):
    pass


class RuntimeKind(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


_ENV_NAME_RE = re.compile(r"[A-Z_][A-Z0-9_]*")
_POLICY_FIELDS = ("speech", "listening", "reasoning", "answering")
_BLUFF_MODES = {"none", "honest", "strategic", "long_con", "learned"}


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model_id_env: str
    api_key_env: str
    temperature: float
    max_output_tokens: int


@dataclass(frozen=True)
class AgentPolicies:
    speech: str
    listening: str
    reasoning: str
    answering: str


@dataclass(frozen=True)
class BluffSettings:
    mode: str
    listen_to_table_talk: bool
    history_window_rounds: int
    private_strategy_memory: bool


@dataclass(frozen=True)
class AgentProfile:
    profile_id: str
    display_name: str
    archetype: str
    runtime_kind: RuntimeKind
    policies: AgentPolicies
    bluff: BluffSettings
    prompt_persona: str | None
    llm: LLMSettings | None
    deterministic_answer_policy: str | None
    strategy_rewrite_interval_rounds: int | None


@dataclass(frozen=True)
class AgentSeat:
    seat: int
    agent_id: str
    profile_id: str


@dataclass(frozen=True)
class AgentRoster:
    roster_id: str
    name: str
    initial_agent_count: int
    recommended_agenda_strategy: int
    seats: tuple[AgentSeat, ...]

    def player_ids(self) -> tuple[str, ...]:
        return tuple(seat.agent_id for seat in self.seats)


@dataclass(frozen=True)
class TableTalkContract:
    enabled: bool
    max_chars: int
    messages_per_agent: int
    publish_simultaneously: bool
    communication_after_problem_reveal: bool


@dataclass(frozen=True)
class PublicHistoryContract:
    include: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class AgentCatalog:
    schema_version: str
    profiles: dict[str, AgentProfile]
    rosters: dict[str, AgentRoster]
    table_talk: TableTalkContract
    public_history: PublicHistoryContract
    sha256: str
    path: Path

    def get_profile(self, profile_id: str) -> AgentProfile:
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise AgentConfigError(f"unknown agent profile {profile_id!r}") from exc

    def get_roster(self, roster_id: str) -> AgentRoster:
        try:
            return self.rosters[roster_id]
        except KeyError as exc:
            raise AgentConfigError(f"unknown agent roster {roster_id!r}") from exc

    def roster_metadata(self, roster_id: str) -> dict[str, dict[str, Any]]:
        roster = self.get_roster(roster_id)
        return {
            seat.agent_id: {
                "seat": seat.seat,
                "profile_id": seat.profile_id,
                "display_name": self.profiles[seat.profile_id].display_name,
                "archetype": self.profiles[seat.profile_id].archetype,
                "runtime_kind": self.profiles[seat.profile_id].runtime_kind.value,
                "bluff_mode": self.profiles[seat.profile_id].bluff.mode,
                "listens_to_table_talk": self.profiles[
                    seat.profile_id
                ].bluff.listen_to_table_talk,
            }
            for seat in roster.seats
        }

    def profile_for_agent(self, roster_id: str, agent_id: str) -> AgentProfile:
        roster = self.get_roster(roster_id)
        for seat in roster.seats:
            if seat.agent_id == agent_id:
                return self.profiles[seat.profile_id]
        raise AgentConfigError(f"agent {agent_id!r} is not seated in roster {roster_id!r}")


@dataclass(frozen=True)
class ResolvedLLMRuntime:
    provider: str
    model_id: str
    api_key_env: str
    temperature: float
    max_output_tokens: int


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentConfigError(f"{context} must be an object")
    return value


def _string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentConfigError(f"{context} must be a non-empty string")
    return value


def _env_name(value: Any, context: str) -> str:
    name = _string(value, context)
    if not _ENV_NAME_RE.fullmatch(name):
        raise AgentConfigError(f"{context} must be an uppercase environment variable name")
    return name


def _llm_settings(raw: Any, context: str) -> LLMSettings:
    item = _mapping(raw, context)
    provider = _string(item.get("provider"), f"{context}.provider")
    model_id_env = _env_name(item.get("model_id_env"), f"{context}.model_id_env")
    api_key_env = _env_name(item.get("api_key_env"), f"{context}.api_key_env")
    temperature = item.get("temperature")
    max_output_tokens = item.get("max_output_tokens")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
        raise AgentConfigError(f"{context}.temperature must be numeric")
    if not 0 <= temperature <= 2:
        raise AgentConfigError(f"{context}.temperature must be between 0 and 2")
    if (
        isinstance(max_output_tokens, bool)
        or not isinstance(max_output_tokens, int)
        or max_output_tokens <= 0
    ):
        raise AgentConfigError(f"{context}.max_output_tokens must be positive")
    return LLMSettings(
        provider,
        model_id_env,
        api_key_env,
        float(temperature),
        max_output_tokens,
    )


def load_agent_catalog(path: str | Path) -> AgentCatalog:
    resolved = Path(path).resolve()
    try:
        data = resolved.read_bytes()
    except OSError as exc:
        raise AgentConfigError(f"cannot read {resolved}: {exc}") from exc
    try:
        document = _mapping(yaml.safe_load(data), "agent configuration")
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise AgentConfigError(f"invalid agent YAML: {exc}") from exc

    schema_version = _string(document.get("schema_version"), "schema_version")
    defaults = _llm_settings(document.get("llm_defaults"), "llm_defaults")

    raw_talk = _mapping(document.get("table_talk"), "table_talk")
    if (
        not isinstance(raw_talk.get("enabled"), bool)
        or isinstance(raw_talk.get("max_chars"), bool)
        or not isinstance(raw_talk.get("max_chars"), int)
        or isinstance(raw_talk.get("messages_per_agent"), bool)
        or not isinstance(raw_talk.get("messages_per_agent"), int)
        or not isinstance(raw_talk.get("publish_simultaneously"), bool)
        or not isinstance(raw_talk.get("communication_after_problem_reveal"), bool)
    ):
        raise AgentConfigError("table_talk fields have invalid types")
    table_talk = TableTalkContract(
        enabled=raw_talk.get("enabled"),
        max_chars=raw_talk.get("max_chars"),
        messages_per_agent=raw_talk.get("messages_per_agent"),
        publish_simultaneously=raw_talk.get("publish_simultaneously"),
        communication_after_problem_reveal=raw_talk.get(
            "communication_after_problem_reveal"
        ),
    )
    if table_talk != TableTalkContract(True, 100, 1, True, False):
        raise AgentConfigError("table_talk must match the frozen simultaneous V1 contract")

    raw_history = _mapping(document.get("public_history"), "public_history")
    included = raw_history.get("include")
    excluded = raw_history.get("exclude")
    if not isinstance(included, list) or not all(isinstance(value, str) for value in included):
        raise AgentConfigError("public_history.include must be a string list")
    if not isinstance(excluded, list) or not all(isinstance(value, str) for value in excluded):
        raise AgentConfigError("public_history.exclude must be a string list")
    required_exclusions = {
        "chain_of_thought",
        "private_strategy",
        "internal_confidence",
        "hidden_difficulty",
        "answer_key",
    }
    if not required_exclusions.issubset(excluded):
        raise AgentConfigError("public history must exclude all private and dealer-only fields")
    required_inclusions = {
        "category",
        "table_talk",
        "reasoning_tier",
        "submitted_answer",
        "correct",
        "prize_received_cents",
        "bankroll_after_round_cents",
    }
    if not required_inclusions.issubset(included):
        raise AgentConfigError("public history must include the V1 reputation fields")
    if set(included) & set(excluded):
        raise AgentConfigError("public history fields cannot be both included and excluded")
    public_history = PublicHistoryContract(tuple(included), tuple(excluded))

    raw_profiles = document.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise AgentConfigError("profiles must be a non-empty list")
    profiles: dict[str, AgentProfile] = {}
    for index, raw_profile in enumerate(raw_profiles):
        item = _mapping(raw_profile, f"profiles[{index}]")
        profile_id = _string(item.get("id"), f"profiles[{index}].id")
        if profile_id in profiles:
            raise AgentConfigError(f"duplicate agent profile id: {profile_id}")
        display_name = _string(item.get("display_name"), f"profile {profile_id}.display_name")
        archetype = _string(item.get("archetype"), f"profile {profile_id}.archetype")
        try:
            runtime_kind = RuntimeKind(item.get("runtime"))
        except ValueError as exc:
            raise AgentConfigError(f"profile {profile_id}: invalid runtime") from exc

        raw_policies = _mapping(item.get("policies"), f"profile {profile_id}.policies")
        policies = AgentPolicies(
            *(
                _string(raw_policies.get(field), f"profile {profile_id}.policies.{field}")
                for field in _POLICY_FIELDS
            )
        )
        raw_bluff = _mapping(item.get("bluff"), f"profile {profile_id}.bluff")
        bluff_mode = raw_bluff.get("mode")
        if bluff_mode not in _BLUFF_MODES:
            raise AgentConfigError(f"profile {profile_id}: invalid bluff mode {bluff_mode!r}")
        listen = raw_bluff.get("listen_to_table_talk")
        memory = raw_bluff.get("private_strategy_memory")
        history_window = raw_bluff.get("history_window_rounds")
        if not isinstance(listen, bool) or not isinstance(memory, bool):
            raise AgentConfigError(f"profile {profile_id}: bluff flags must be boolean")
        if (
            isinstance(history_window, bool)
            or not isinstance(history_window, int)
            or not 0 <= history_window <= 25
        ):
            raise AgentConfigError(f"profile {profile_id}: history window must be 0 through 25")
        bluff = BluffSettings(bluff_mode, listen, history_window, memory)

        prompt_persona = item.get("prompt_persona")
        llm: LLMSettings | None = None
        deterministic_policy: str | None = None
        if runtime_kind == RuntimeKind.LLM:
            prompt_persona = _string(prompt_persona, f"profile {profile_id}.prompt_persona")
            raw_override = item.get("llm", {})
            override = _mapping(raw_override, f"profile {profile_id}.llm")
            merged = {
                "provider": override.get("provider", defaults.provider),
                "model_id_env": override.get("model_id_env", defaults.model_id_env),
                "api_key_env": override.get("api_key_env", defaults.api_key_env),
                "temperature": override.get("temperature", defaults.temperature),
                "max_output_tokens": override.get(
                    "max_output_tokens", defaults.max_output_tokens
                ),
            }
            llm = _llm_settings(merged, f"profile {profile_id}.llm")
        else:
            if prompt_persona is not None or item.get("llm") is not None:
                raise AgentConfigError(
                    f"profile {profile_id}: deterministic runtime cannot declare LLM settings"
                )
            deterministic_policy = _string(
                item.get("deterministic_answer_policy"),
                f"profile {profile_id}.deterministic_answer_policy",
            )

        rewrite_interval = item.get("strategy_rewrite_interval_rounds")
        if rewrite_interval is not None and (
            isinstance(rewrite_interval, bool)
            or not isinstance(rewrite_interval, int)
            or rewrite_interval <= 0
        ):
            raise AgentConfigError(
                f"profile {profile_id}: strategy rewrite interval must be positive"
            )
        profiles[profile_id] = AgentProfile(
            profile_id,
            display_name,
            archetype,
            runtime_kind,
            policies,
            bluff,
            prompt_persona,
            llm,
            deterministic_policy,
            rewrite_interval,
        )

    raw_rosters = document.get("rosters")
    if not isinstance(raw_rosters, list) or not raw_rosters:
        raise AgentConfigError("rosters must be a non-empty list")
    rosters: dict[str, AgentRoster] = {}
    for index, raw_roster in enumerate(raw_rosters):
        item = _mapping(raw_roster, f"rosters[{index}]")
        roster_id = _string(item.get("id"), f"rosters[{index}].id")
        if roster_id in rosters:
            raise AgentConfigError(f"duplicate roster id: {roster_id}")
        name = _string(item.get("name"), f"roster {roster_id}.name")
        count = item.get("initial_agent_count")
        if isinstance(count, bool) or not isinstance(count, int) or not 3 <= count <= 10:
            raise AgentConfigError(
                f"roster {roster_id}: initial_agent_count must be between 3 and 10"
            )
        strategy = item.get("recommended_agenda_strategy")
        if isinstance(strategy, bool) or not isinstance(strategy, int) or strategy <= 0:
            raise AgentConfigError(
                f"roster {roster_id}: agenda strategy must be a positive integer"
            )
        raw_seats = item.get("seats")
        if not isinstance(raw_seats, list) or len(raw_seats) != count:
            raise AgentConfigError(f"roster {roster_id}: seat count does not match")
        seats: list[AgentSeat] = []
        agent_ids: set[str] = set()
        for expected_seat, raw_seat in enumerate(raw_seats, start=1):
            seat_item = _mapping(raw_seat, f"roster {roster_id} seat {expected_seat}")
            if seat_item.get("seat") != expected_seat:
                raise AgentConfigError(f"roster {roster_id}: seats must be consecutive from 1")
            agent_id = _string(seat_item.get("agent_id"), "agent_id")
            profile_id = _string(seat_item.get("profile_id"), "profile_id")
            if agent_id in agent_ids:
                raise AgentConfigError(f"roster {roster_id}: duplicate agent_id {agent_id!r}")
            if profile_id not in profiles:
                raise AgentConfigError(
                    f"roster {roster_id}: unknown profile_id {profile_id!r}"
                )
            agent_ids.add(agent_id)
            seats.append(AgentSeat(expected_seat, agent_id, profile_id))
        rosters[roster_id] = AgentRoster(roster_id, name, count, strategy, tuple(seats))

    return AgentCatalog(
        schema_version,
        profiles,
        rosters,
        table_talk,
        public_history,
        hashlib.sha256(data).hexdigest(),
        resolved,
    )


def resolve_llm_runtime(
    profile: AgentProfile,
    environ: Mapping[str, str] | None = None,
    *,
    require_api_key: bool = True,
) -> ResolvedLLMRuntime:
    if profile.runtime_kind != RuntimeKind.LLM or profile.llm is None:
        raise AgentConfigError(f"profile {profile.profile_id!r} is not LLM-driven")
    environment = os.environ if environ is None else environ
    model_id = environment.get(profile.llm.model_id_env, "").strip()
    if not model_id:
        raise AgentConfigError(
            f"missing model identifier environment variable {profile.llm.model_id_env}"
        )
    if require_api_key and not environment.get(profile.llm.api_key_env, "").strip():
        raise AgentConfigError(
            f"missing API credential environment variable {profile.llm.api_key_env}"
        )
    return ResolvedLLMRuntime(
        profile.llm.provider,
        model_id,
        profile.llm.api_key_env,
        profile.llm.temperature,
        profile.llm.max_output_tokens,
    )


def prepare_agent_context(
    payload: Mapping[str, Any],
    profile: AgentProfile,
) -> dict[str, Any]:
    """Apply the profile's listening boundary without mutating dealer state."""
    prepared = deepcopy(dict(payload))
    if profile.bluff.listen_to_table_talk:
        return prepared
    prepared.pop("public_messages", None)
    history = prepared.get("public_history")
    if isinstance(history, list):
        for round_record in history:
            if isinstance(round_record, dict):
                round_record.pop("table_talk", None)
    return prepared
