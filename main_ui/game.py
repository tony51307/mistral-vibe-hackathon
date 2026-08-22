"""Streamlit-facing adapter around the canonical dealer core."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from metrics import attach_bankroll, empty_stats, summary, update_after_round
from prompts import CHEAP_SYSTEM, DEEP_SYSTEM, cheap_user, deep_user

REPO_ROOT = Path(__file__).resolve().parents[1]
DEALER_ROOT = REPO_ROOT / "dealer"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(DEALER_ROOT) not in sys.path:
    sys.path.insert(0, str(DEALER_ROOT))

from dealer.game.agent_config import load_agent_catalog
from dealer.game.dealer_distributor import DealerGame, SeasonComplete
from dealer.game.loaders import load_agendas, load_problem_bank
from dealer.game.models import GameConfig as DealerGameConfig
from dealer.game.reasoning_provider import Router, Solver
from mistral_client import ModelProvider

DEFAULT_ROSTER_ID = "social_3"
DEFAULT_ENTRY_FEE = 15
HIGH_STAKES_POT = 100
CODE_FENCE_MIN_LINES = 2

TIER_PRICE = {"none": 1, "low": 2, "medium": 3, "high": 5, "xhigh": 9}

REASONING_EFFORT_BY_TIER = {
    "none": None,
    "low": "none",
    "medium": "high",
    "high": "high",
    "xhigh": "high",
}


def agenda_labels() -> dict[int, str]:
    bank = load_problem_bank(DEALER_ROOT / "data/pay_to_think_problem_bank_v1.json")
    agendas = load_agendas(DEALER_ROOT / "data/pay_to_think_agendas_v1.yaml", bank)
    return {
        number: _display_agenda_name(agenda.name)
        for number, agenda in sorted(agendas.agendas.items())
    }


def _display_agenda_name(name: str) -> str:
    return name.replace("_", " ").title()


def _thinking_label(policy: str) -> str:
    match policy:
        case "always_none":
            return "No thinker"
        case "always_high":
            return "Always thinker"
        case "perturbation_router":
            return "Dynamic auto-thinker"
        case "kelly_value" | "opponent_aware" | "dynamic" | "learned":
            return "Dynamic thinker"
        case _:
            return _display_agenda_name(policy)


def roster_labels() -> dict[str, str]:
    catalog = load_agent_catalog(DEALER_ROOT / "agents/agent_rosters_v1.yaml")
    return {
        roster_id: f"{roster.name} ({roster.initial_agent_count} agents)"
        for roster_id, roster in catalog.rosters.items()
    }


@dataclass
class GameConfig:
    start_bankroll: int = 80
    entrance_fee: int = DEFAULT_ENTRY_FEE
    dealer_contribution: int = 12
    agent_roster: str = DEFAULT_ROSTER_ID
    n_rounds: int = 25
    strategy_number: int = 5
    seed: int = 260822
    use_live_api: bool = True
    model_provider: ModelProvider = "mistral"
    enable_bluffing: bool = False


@dataclass
class GameState:
    config: GameConfig
    dealer: DealerGame
    player_ids: tuple[str, ...]
    display_names: dict[str, str]
    profile_ids: dict[str, str]
    policies: dict[str, str]
    thinking_labels: dict[str, str]
    bluff_modes: dict[str, str]
    listens_to_talk: dict[str, bool]
    round_index: int = 0
    prize_pool: int = 0
    bankrolls: dict[str, int] = field(default_factory=dict)
    stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    finished: bool = False


def dollars(cents: int | float) -> float:
    return round(cents / 100, 2)


def cents(dollars_value: int | float) -> int:
    return int(round(dollars_value * 100))


def new_game(config: GameConfig) -> GameState:
    bank = load_problem_bank(DEALER_ROOT / "data/pay_to_think_problem_bank_v1.json")
    agendas = load_agendas(DEALER_ROOT / "data/pay_to_think_agendas_v1.yaml", bank)
    agent_catalog = load_agent_catalog(DEALER_ROOT / "agents/agent_rosters_v1.yaml")
    roster = agent_catalog.get_roster(config.agent_roster)
    dealer_config = DealerGameConfig.for_table_size(
        roster.initial_agent_count, entry_fee_cents=cents(config.entrance_fee)
    )
    dealer = DealerGame(
        player_ids=roster.player_ids(),
        problem_bank=bank,
        agenda_catalog=agendas,
        strategy_number=config.strategy_number,
        seed=config.seed,
        config=dealer_config,
        table_mode_id=f"streamlit_demo:{roster.roster_id}",
        agent_roster_id=roster.roster_id,
        agent_config_sha256=agent_catalog.sha256,
        agent_metadata=agent_catalog.roster_metadata(roster.roster_id),
        model_identifier="streamlit-demo",
    )
    config.start_bankroll = int(dollars(dealer.config.starting_bankroll_cents))
    config.entrance_fee = int(dollars(dealer.config.entry_fee_cents))
    config.dealer_contribution = int(dollars(dealer.config.dealer_contribution_cents))
    config.n_rounds = dealer.config.season_rounds
    player_ids = roster.player_ids()
    metadata = agent_catalog.roster_metadata(config.agent_roster)
    display_names = {
        agent_id: str(metadata[agent_id]["display_name"]) for agent_id in player_ids
    }
    profile_ids = {
        agent_id: str(metadata[agent_id]["profile_id"]) for agent_id in player_ids
    }
    policies = {
        agent_id: agent_catalog.profile_for_agent(
            config.agent_roster, agent_id
        ).policies.reasoning
        for agent_id in player_ids
    }
    thinking_labels = {
        agent_id: _thinking_label(policies[agent_id]) for agent_id in player_ids
    }
    bluff_modes = {
        agent_id: str(metadata[agent_id]["bluff_mode"]) for agent_id in player_ids
    }
    listens_to_talk = {
        agent_id: bool(metadata[agent_id]["listens_to_table_talk"])
        for agent_id in player_ids
    }
    return GameState(
        config=config,
        dealer=dealer,
        player_ids=player_ids,
        display_names=display_names,
        profile_ids=profile_ids,
        policies=policies,
        thinking_labels=thinking_labels,
        bluff_modes=bluff_modes,
        listens_to_talk=listens_to_talk,
        bankrolls={name: config.start_bankroll for name in display_names.values()},
        stats={
            name: empty_stats(name, config.start_bankroll)
            for name in display_names.values()
        },
    )


def play_round(state: GameState, client: Any) -> dict[str, Any]:
    if state.finished:
        return {"finished": True}

    dealer = deepcopy(state.dealer)
    try:
        category_payloads = dealer.reveal_category()
    except SeasonComplete:
        state.finished = True
        return {"finished": True}

    round_number = next(iter(category_payloads.values()))["round"]
    dealer.collect_entries()
    messages = (
        _table_talk(category_payloads, state) if state.config.enable_bluffing else {}
    )
    display_messages = dealer.record_table_talk(messages)
    problem_payloads = dealer.reveal_problem()
    routers = {
        agent_id: _router(
            agent_id,
            round_number,
            state.policies.get(agent_id, "dynamic"),
            state.config.enable_bluffing and state.listens_to_talk.get(agent_id, False),
        )
        for agent_id in problem_payloads
    }
    dealer.route_and_purchase(routers)
    solvers = {
        agent_id: _solver(
            agent_id,
            dealer.problem_bank.problems[payload["problem_id"]],
            client if state.config.use_live_api else None,
        )
        for agent_id, payload in problem_payloads.items()
    }
    dealer.solve(solvers)
    dealer.judge()
    dealer.payout()
    event = dealer.complete_round()
    state.dealer = dealer
    public_problem = next(iter(problem_payloads.values()))
    record = _record_from_event(event, display_messages, public_problem, state)
    _update_state_after_event(state, record, event)
    return record


def _table_talk(
    category_payloads: Mapping[str, Mapping[str, Any]], state: GameState
) -> dict[str, str]:
    messages: dict[str, str] = {}
    for agent_id in state.player_ids:
        if agent_id not in category_payloads:
            continue
        payload = category_payloads[agent_id]
        previous = tuple(messages.values())
        messages[agent_id] = _truncate_table_talk(
            _bluff_message(agent_id, payload, state, previous)
        )
    return messages


def _bluff_message(  # noqa: PLR0911
    agent_id: str,
    payload: Mapping[str, Any],
    state: GameState,
    previous_messages: tuple[str, ...],
) -> str:
    category = str(payload["category"]).replace("_", " ")
    name = state.display_names[agent_id]
    mode = state.bluff_modes.get(agent_id, "none")
    policy = state.policies.get(agent_id, "dynamic")
    pot = dollars(int(payload["current_rollover_cents"]))
    heard_pressure = any(
        token in message.casefold()
        for message in previous_messages
        for token in ("strong", "high", "xhigh", "big pot", "spending")
    )
    if mode in {"strategic", "long_con", "learned"}:
        if heard_pressure:
            return f"{name}: {category} looks crowded. I may save chips and let others overpay."
        return f"{name}: {category} is one of my strongest spots; expect a serious bid."
    if mode == "honest":
        if policy in {"always_high", "kelly_value", "opponent_aware"}:
            return f"{name}: I respect {category}; if the pot is live I will pay for confidence."
        return f"{name}: I am watching bankrolls, not making a big claim on {category}."
    if policy == "always_high":
        return f"{name}: {category} is worth depth. I am likely buying high reasoning."
    if policy == "always_none":
        return f"{name}: I am keeping this cheap unless forced. No fancy reasoning."
    if pot > 0:
        return f"{name}: Rollover is ${pot}; I expect aggressive bids this hand."
    return f"{name}: {category} is uncertain. I will decide after hearing the table."


def _truncate_table_talk(
    message: str, max_words: int = 50, max_chars: int = 100
) -> str:
    words = message.split()
    if len(words) > max_words:
        message = " ".join(words[:max_words])
    if len(message) > max_chars:
        message = message[: max_chars - 1].rstrip() + "…"
    return message


def _router(
    agent_id: str, round_number: int, policy: str, listens_to_talk: bool
) -> Router:
    def route(payload: Mapping[str, Any]) -> dict[str, str]:
        affordable = set(payload["affordable_tiers"])
        pot = dollars(payload["pot_cents"])
        if policy == "always_none":
            tier = "none"
        elif policy == "always_high":
            tier = (
                "xhigh" if pot >= HIGH_STAKES_POT or round_number % 8 == 0 else "high"
            )
        elif policy in {"kelly_value", "opponent_aware"}:
            tier = "medium" if round_number % 3 == 0 else "low"
        else:
            tier = _dynamic_tier(payload, round_number)
        if listens_to_talk:
            tier = _adjust_tier_for_table_talk(tier, payload.get("public_messages", {}))
        if tier in affordable:
            return {"reasoning_tier": tier}
        for fallback in ("high", "medium", "low", "none"):
            if fallback in affordable:
                return {"reasoning_tier": fallback}
        return {"reasoning_tier": "none"}

    return route


def _adjust_tier_for_table_talk(tier: str, public_messages: Any) -> str:
    if not isinstance(public_messages, Mapping):
        return tier
    table_text = " ".join(
        str(message).casefold() for message in public_messages.values()
    )
    if any(
        token in table_text
        for token in ("strongest", "high reasoning", "xhigh", "serious bid", "overpay")
    ):
        return _raise_tier(tier)
    if any(
        token in table_text
        for token in ("save chips", "keeping this cheap", "not worth", "crowded")
    ):
        return _lower_tier(tier)
    return tier


def _raise_tier(tier: str) -> str:
    order = ("none", "low", "medium", "high", "xhigh")
    return order[min(len(order) - 1, order.index(tier) + 1)]


def _lower_tier(tier: str) -> str:
    order = ("none", "low", "medium", "high", "xhigh")
    return order[max(0, order.index(tier) - 1)]


def _dynamic_tier(payload: Mapping[str, Any], round_number: int) -> str:
    category = str(payload["category"])
    pot = dollars(payload["pot_cents"])
    score = _score(str(payload["problem_id"]), round_number, pot)
    disagreement = category in {"probability", "algorithms", "logic"} or score % 5 == 0
    high_risk = pot >= HIGH_STAKES_POT or score % 11 == 0
    if high_risk and disagreement:
        return "xhigh" if score % 4 == 0 else "high"
    if disagreement:
        return "high" if score % 3 == 0 else "medium"
    if high_risk:
        return "medium"
    return "low" if score % 4 else "none"


def _solver(agent_id: str, problem: dict[str, Any], client: Any | None) -> Solver:
    def solve(payload: Mapping[str, Any]) -> dict[str, Any]:
        tier = str(payload["reasoning_tier"])
        if client is not None and getattr(client, "available", False):
            try:
                return _live_solver_response(client, payload, tier)
            except RuntimeError as exc:
                return _offline_solver_response(
                    agent_id,
                    problem,
                    tier,
                    model="offline-rate-limit-fallback",
                    error=str(exc),
                )
        return _offline_solver_response(
            agent_id, problem, tier, model="offline-dealer-demo"
        )

    return solve


def _offline_solver_response(
    agent_id: str,
    problem: dict[str, Any],
    tier: str,
    *,
    model: str,
    error: str | None = None,
) -> dict[str, Any]:
    answer = problem["answer"]["display"]
    if not _mock_correct(agent_id, str(problem["id"]), tier, problem):
        answer = _wrong_answer(problem)
    response = {"answer": answer, "model": model, "api_reasoning_configuration": tier}
    if error:
        response["provider_error"] = error[:240]
    return response


def _live_solver_response(
    client: Any, payload: Mapping[str, Any], tier: str
) -> dict[str, Any]:
    prompt = str(payload["prompt_markdown"])
    tier_note = f"\n\nAllowed reasoning tier bid: {tier}"
    strong = tier in {"medium", "high", "xhigh"}
    data = client.chat_json(
        system=DEEP_SYSTEM if strong else CHEAP_SYSTEM,
        user=deep_user(f"{prompt}{tier_note}")
        if strong
        else cheap_user(f"{prompt}{tier_note}"),
        strong=strong,
        temperature=0.1 if strong else 0.0,
        reasoning_effort=REASONING_EFFORT_BY_TIER[tier],
        max_tokens=256,
    )
    answer = _extract_live_answer(data)
    usage = data.get("_usage") if isinstance(data.get("_usage"), dict) else {}
    response: dict[str, Any] = {
        "answer": answer,
        "model": str(data.get("_model", "mistral-live")),
        "api_reasoning_configuration": tier,
    }
    if usage.get("prompt_tokens") is not None:
        response["actual_input_tokens"] = usage["prompt_tokens"]
    if usage.get("completion_tokens") is not None:
        response["actual_output_tokens"] = usage["completion_tokens"]
    if data.get("_latency_ms") is not None:
        response["latency_ms"] = data["_latency_ms"]
    return response


def _extract_live_answer(data: Mapping[str, Any]) -> str:
    answer = data.get("answer", "")
    if isinstance(answer, Mapping):
        answer = answer.get("answer", "")
    if isinstance(answer, str) and answer.strip().startswith("{"):
        try:
            nested = json.loads(answer)
        except json.JSONDecodeError:
            nested = None
        if isinstance(nested, Mapping):
            answer = nested.get("answer", answer)
    normalized = str(answer).strip()
    if normalized.startswith("```"):
        normalized = _strip_code_fence(normalized)
    if normalized.startswith("{"):
        try:
            nested = json.loads(normalized)
        except json.JSONDecodeError:
            nested = None
        if isinstance(nested, Mapping):
            normalized = str(nested.get("answer", normalized)).strip()
    scalar = _first_scalar_answer(normalized)
    if scalar:
        return scalar
    if normalized:
        return normalized
    return str(data.get("raw", "")).strip()


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    lines = stripped.splitlines()
    if (
        len(lines) >= CODE_FENCE_MIN_LINES
        and lines[0].startswith("```")
        and lines[-1].strip() == "```"
    ):
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _first_scalar_answer(text: str) -> str:
    stripped = text.strip().strip("$")
    if not stripped:
        return ""
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?", stripped):
        return stripped
    match = re.search(r'"answer"\s*:\s*"([^"]+)"', stripped)
    if match:
        return match.group(1).strip()
    match = re.search(
        r"(?i)(?:final answer|answer)\s*(?:is|:)\s*([+-]?\d+(?:\.\d+)?(?:/\d+)?)",
        stripped,
    )
    if match:
        return match.group(1).strip()
    numbers = re.findall(r"[+-]?\d+(?:\.\d+)?(?:/\d+)?", stripped)
    if len(numbers) == 1:
        return numbers[0]
    return ""


def _mock_correct(
    agent_id: str, problem_id: str, tier: str, problem: dict[str, Any]
) -> bool:
    difficulty = problem["dealer_meta"]["difficulty"]
    probabilities = {
        "trivial": {
            "none": 0.92,
            "low": 0.95,
            "medium": 0.97,
            "high": 0.99,
            "xhigh": 0.99,
        },
        "easy": {
            "none": 0.82,
            "low": 0.88,
            "medium": 0.93,
            "high": 0.97,
            "xhigh": 0.99,
        },
        "medium": {
            "none": 0.52,
            "low": 0.62,
            "medium": 0.76,
            "high": 0.86,
            "xhigh": 0.91,
        },
        "hard": {
            "none": 0.25,
            "low": 0.36,
            "medium": 0.54,
            "high": 0.70,
            "xhigh": 0.80,
        },
        "very_hard": {
            "none": 0.12,
            "low": 0.22,
            "medium": 0.36,
            "high": 0.54,
            "xhigh": 0.66,
        },
    }
    probability = probabilities.get(difficulty, probabilities["medium"])[tier]
    if agent_id == "dynamic" and tier in {"high", "xhigh"}:
        probability = min(0.95, probability + 0.07)
    sample = _score(f"{agent_id}:{problem_id}:{tier}", len(problem_id), 0) / 100
    return sample < probability


def _wrong_answer(problem: dict[str, Any]) -> str:
    validator = problem["answer"]["validator"]
    kind = validator["kind"]
    if kind == "integer":
        return str(int(validator["value"]) + 1)
    if kind == "numeric":
        return str(float(validator["value"]) + 1)
    if kind == "boolean":
        return "false" if validator["value"] else "true"
    return "unknown"


def _score(*parts: object) -> int:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode()).hexdigest()
    return int(digest[:8], 16) % 100


def _record_from_event(
    event: dict[str, Any],
    display_messages: dict[str, str],
    public_problem: Mapping[str, Any],
    state: GameState,
) -> dict[str, Any]:
    agents = {row["agent_id"]: row for row in event["agents"]}
    display_names = state.display_names
    winners = [display_names[agent_id] for agent_id in event["winner_ids"]]
    entries = [
        {
            "agent": display_names[agent_id],
            "decision": "SHOW HAND" if row["show_hand"] else "ENTER",
            "entrance_fee": dollars(row["entry_paid_cents"]),
            "message": display_messages.get(agent_id, ""),
        }
        for agent_id, row in agents.items()
    ]
    public_actions = [
        {
            "agent": display_names[agent_id],
            "action": "THINK",
            "think_credits": dollars(row["reasoning_price_cents"]),
            "policy": state.policies.get(agent_id, "dynamic"),
        }
        for agent_id, row in agents.items()
    ]
    dealer_actions = [
        {
            "agent": display_names[agent_id],
            "action": "THINK",
            "think_credits": dollars(row["reasoning_price_cents"]),
            "answer": row["submitted_answer"],
            "tier": row["router_tier"],
            "correct": row["correct"],
            "dealer": {
                "show_hand": row["show_hand"],
                "router_fallback": row["router_fallback"],
                "router_attempts": row["router_attempts"],
                "judge": row["judge"],
                "trace": _autothink_trace(agent_id, row, event, state),
            },
            "metrics": _agent_metrics(agent_id, row, state),
        }
        for agent_id, row in agents.items()
    ]
    payouts = {
        display_names[agent_id]: dollars(row["prize_received_cents"])
        for agent_id, row in agents.items()
    }
    problem = {
        "id": event["problem_id"],
        "question": str(public_problem["prompt_markdown"]),
        "answer": event["correct_answer"],
        "explanation": "Validated by the canonical dealer answer key.",
        "difficulty": event["hidden_difficulty"],
        "category": event["category"],
    }
    return {
        "finished": False,
        "round": event["round"],
        "announcement": {
            "round": event["round"],
            "category": event["category"],
            "base_prize": dollars(event["dealer_contribution_cents"]),
            "rollover": dollars(event["rollover_in_cents"]),
            "entrance_fee": dollars(next(iter(agents.values()))["entry_paid_cents"]),
        },
        "problem": problem,
        "phase1": {
            "entries": entries,
            "entered": [entry["agent"] for entry in entries],
            "prize_pool": dollars(event["pot_cents"]),
            "public_bankrolls_after_entry": {
                display_names[agent_id]: dollars(row["bankroll_after_entry_cents"])
                for agent_id, row in agents.items()
            },
        },
        "cycles": [
            {
                "public": {
                    "cycle": 1,
                    "actions": public_actions,
                    "submitted_count": len(public_actions),
                    "winner_announced": bool(winners),
                    "winners": winners,
                    "dealer_announcement": (
                        f"Prize split among: {', '.join(winners)}."
                        if winners
                        else "No correct answer. Pot rolls forward."
                    ),
                },
                "dealer": dealer_actions,
            }
        ],
        "winners": winners,
        "payouts": payouts,
        "payout_each": dollars(event["pot_cents"] // max(1, len(winners)))
        if winners
        else 0,
        "prize": dollars(event["pot_cents"]),
        "rollover": dollars(event["rollover_out_cents"]),
        "bankrolls": {
            display_names[agent_id]: dollars(row["bankroll_after_round_cents"])
            for agent_id, row in agents.items()
        },
        "dealer_event": event,
    }


def _autothink_trace(
    agent_id: str, row: dict[str, Any], event: dict[str, Any], state: GameState
) -> dict[str, Any]:
    if state.policies.get(agent_id) not in {
        "perturbation_router",
        "dynamic",
        "learned",
    }:
        return {}
    tier = row["router_tier"]
    paid = tier in {"high", "xhigh"}
    return {
        "cheap_answer": "router baseline",
        "perturbed_answers": [row["router_tier"], "critical perspective"],
        "stability": "LOW" if paid else "HIGH",
        "pay_to_think": paid,
        "deep_answer": row["submitted_answer"] if paid else None,
        "changed_answer": paid,
        "reason": f"Dealer pot ${dollars(event['pot_cents'])} routed to {tier}.",
    }


def _agent_metrics(
    agent_id: str, row: dict[str, Any], state: GameState
) -> dict[str, Any]:
    tier = row["router_tier"]
    return {
        "cheap_calls": 1 if tier in {"none", "low"} else 0,
        "perturbation_calls": 2 if agent_id == "dynamic" else 0,
        "deep_calls": 1 if tier in {"high", "xhigh"} else 0,
        "deep_triggered": agent_id == "dynamic" and tier in {"high", "xhigh"},
        "changed_answer": state.policies.get(agent_id) == "perturbation_router"
        and tier in {"high", "xhigh"},
    }


def _update_state_after_event(
    state: GameState, record: dict[str, Any], event: dict[str, Any]
) -> None:
    for row in event["agents"]:
        name = state.display_names[row["agent_id"]]
        spent = dollars(row["entry_paid_cents"] + row["reasoning_price_cents"])
        payout = dollars(row["prize_received_cents"])
        update_after_round(
            state.stats[name],
            {
                "decision": "ENTER",
                "spent": spent,
                "correct": bool(row["correct"]),
                "submitted": True,
                "payout": payout,
                "metrics": _agent_metrics(row["agent_id"], row, state),
            },
        )
        state.bankrolls[name] = dollars(row["bankroll_after_round_cents"])
        attach_bankroll(state.stats[name], state.bankrolls[name])

    state.prize_pool = dollars(event["rollover_out_cents"])
    state.round_index = event["round"]
    state.history.append(record)
    if state.round_index >= state.config.n_rounds or event.get("season_result"):
        state.finished = True
        record["final_summary"] = summary(
            list(state.stats.values()), state.stats.get("Dynamic")
        )
