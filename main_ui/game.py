"""Streamlit-facing adapter around the canonical dealer core."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import sys
from typing import Any

from metrics import attach_bankroll, empty_stats, summary, update_after_round

REPO_ROOT = Path(__file__).resolve().parents[1]
DEALER_ROOT = REPO_ROOT / "dealer"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(DEALER_ROOT) not in sys.path:
    sys.path.insert(0, str(DEALER_ROOT))

from dealer.game.dealer_distributor import DealerGame, SeasonComplete
from dealer.game.loaders import load_agendas, load_problem_bank
from dealer.game.models import GameConfig as DealerConfig
from dealer.game.reasoning_provider import Router, Solver
from mistral_client import MistralClient, ModelProvider, extract_answer

PLAYER_IDS = ("fast", "always_think", "dynamic", "control")
DISPLAY_NAMES = {
    "fast": "Fast",
    "always_think": "Always Think",
    "dynamic": "Dynamic",
    "control": "Control",
}
DISPLAY_TO_ID = {display: agent_id for agent_id, display in DISPLAY_NAMES.items()}

POLICY_BY_ID = {
    "fast": "cheap-only",
    "always_think": "always-deep",
    "dynamic": "autothink",
    "control": "balanced",
}

TIER_PRICE = {"none": 1, "low": 2, "medium": 3, "high": 5, "xhigh": 9}
HIGH_STAKES_POT = 100


@dataclass
class GameConfig:
    start_bankroll: int = 80
    entrance_fee: int = 10
    dealer_contribution: int = 12
    n_rounds: int = 25
    strategy_number: int = 3
    seed: int = 260822
    use_live_api: bool = False
    model_provider: ModelProvider = "mistral"


@dataclass
class GameState:
    config: GameConfig
    dealer: DealerGame
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
    dealer_config = DealerConfig(
        starting_bankroll_cents=cents(config.start_bankroll),
        entry_fee_cents=cents(config.entrance_fee),
        dealer_contribution_cents=cents(config.dealer_contribution),
        season_rounds=config.n_rounds,
    )
    dealer = DealerGame(
        player_ids=PLAYER_IDS,
        problem_bank=bank,
        agenda_catalog=agendas,
        strategy_number=config.strategy_number,
        seed=config.seed,
        config=dealer_config,
        model_identifier="streamlit-demo",
    )
    return GameState(
        config=config,
        dealer=dealer,
        bankrolls={name: config.start_bankroll for name in DISPLAY_NAMES.values()},
        stats={
            name: empty_stats(name, config.start_bankroll)
            for name in DISPLAY_NAMES.values()
        },
    )


def play_round(state: GameState, client: MistralClient) -> dict[str, Any]:
    if state.finished:
        return {"finished": True}

    try:
        category_payloads = state.dealer.reveal_category()
    except SeasonComplete:
        state.finished = True
        return {"finished": True}

    round_number = next(iter(category_payloads.values()))["round"]
    state.dealer.collect_entries()
    messages = _table_talk(category_payloads)
    display_messages = state.dealer.record_table_talk(messages)
    problem_payloads = state.dealer.reveal_problem()
    routers = {
        agent_id: _router(agent_id, round_number) for agent_id in problem_payloads
    }
    state.dealer.route_and_purchase(routers)
    solvers = {
        agent_id: _solver(
            agent_id,
            state.dealer.problem_bank.problems[payload["problem_id"]],
            client,
            state.config.use_live_api,
        )
        for agent_id, payload in problem_payloads.items()
    }
    state.dealer.solve(solvers)
    state.dealer.judge()
    state.dealer.payout()
    event = state.dealer.complete_round()
    public_problem = next(iter(problem_payloads.values()))
    record = _record_from_event(event, display_messages, public_problem)
    _update_state_after_event(state, record, event)
    return record


def _table_talk(category_payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    messages = {
        "fast": "{category}: fast read, low spend.",
        "always_think": "{category}: buying depth if the stack allows.",
        "dynamic": "{category}: routing first, spend only on instability.",
        "control": "{category}: balanced tier, steady stack.",
    }
    return {
        agent_id: messages[agent_id].format(category=payload["category"].title())
        for agent_id, payload in category_payloads.items()
    }


def _router(agent_id: str, round_number: int) -> Router:
    def route(payload: Mapping[str, Any]) -> dict[str, str]:
        affordable = set(payload["affordable_tiers"])
        pot = dollars(payload["pot_cents"])
        if agent_id == "fast":
            tier = "none"
        elif agent_id == "always_think":
            tier = (
                "xhigh" if pot >= HIGH_STAKES_POT or round_number % 8 == 0 else "high"
            )
        elif agent_id == "control":
            tier = "medium" if round_number % 3 == 0 else "low"
        else:
            tier = _dynamic_tier(payload, round_number)
        if tier in affordable:
            return {"reasoning_tier": tier}
        for fallback in ("high", "medium", "low", "none"):
            if fallback in affordable:
                return {"reasoning_tier": fallback}
        return {"reasoning_tier": "none"}

    return route


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


def _solver(
    agent_id: str, problem: dict[str, Any], client: MistralClient, use_live_api: bool
) -> Solver:
    def solve(payload: Mapping[str, Any]) -> dict[str, Any]:
        tier = str(payload["reasoning_tier"])
        if use_live_api and client.enabled:
            result = client.complete(
                _solver_prompt(problem["prompt_markdown"], tier), tier
            )
            return {
                "answer": extract_answer(result.text),
                "actual_input_tokens": result.input_tokens,
                "actual_output_tokens": result.output_tokens,
                "latency_ms": result.latency_ms,
                "model": f"{result.provider}/{result.model}",
                "api_reasoning_configuration": tier,
            }

        answer = problem["answer"]["display"]
        if not _mock_correct(agent_id, str(problem["id"]), tier, problem):
            answer = _wrong_answer(problem)
        return {
            "answer": answer,
            "model": "offline-dealer-demo",
            "api_reasoning_configuration": tier,
        }

    return solve


def _solver_prompt(question: str, tier: str) -> str:
    return f"""You are playing a short-answer reasoning game.
Reasoning tier purchased: {tier}

Return JSON only:
{{"answer": "short final answer"}}

Problem:
{question}
"""


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
) -> dict[str, Any]:
    agents = {row["agent_id"]: row for row in event["agents"]}
    winners = [DISPLAY_NAMES[agent_id] for agent_id in event["winner_ids"]]
    entries = [
        {
            "agent": DISPLAY_NAMES[agent_id],
            "decision": "SHOW HAND" if row["show_hand"] else "ENTER",
            "entrance_fee": dollars(row["entry_paid_cents"]),
            "message": display_messages.get(agent_id, ""),
        }
        for agent_id, row in agents.items()
    ]
    public_actions = [
        {
            "agent": DISPLAY_NAMES[agent_id],
            "action": "THINK",
            "think_credits": dollars(row["reasoning_price_cents"]),
            "policy": POLICY_BY_ID[agent_id],
        }
        for agent_id, row in agents.items()
    ]
    dealer_actions = [
        {
            "agent": DISPLAY_NAMES[agent_id],
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
                "trace": _autothink_trace(agent_id, row, event),
            },
            "metrics": _agent_metrics(agent_id, row),
        }
        for agent_id, row in agents.items()
    ]
    payouts = {
        DISPLAY_NAMES[agent_id]: dollars(row["prize_received_cents"])
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
                DISPLAY_NAMES[agent_id]: dollars(row["bankroll_after_entry_cents"])
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
            DISPLAY_NAMES[agent_id]: dollars(row["bankroll_after_round_cents"])
            for agent_id, row in agents.items()
        },
        "dealer_event": event,
    }


def _autothink_trace(
    agent_id: str, row: dict[str, Any], event: dict[str, Any]
) -> dict[str, Any]:
    if agent_id != "dynamic":
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


def _agent_metrics(agent_id: str, row: dict[str, Any]) -> dict[str, Any]:
    tier = row["router_tier"]
    return {
        "cheap_calls": 1 if tier in {"none", "low"} else 0,
        "perturbation_calls": 2 if agent_id == "dynamic" else 0,
        "deep_calls": 1 if tier in {"high", "xhigh"} else 0,
        "deep_triggered": agent_id == "dynamic" and tier in {"high", "xhigh"},
        "changed_answer": agent_id == "dynamic" and tier in {"high", "xhigh"},
    }


def _update_state_after_event(
    state: GameState, record: dict[str, Any], event: dict[str, Any]
) -> None:
    for row in event["agents"]:
        name = DISPLAY_NAMES[row["agent_id"]]
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
                "metrics": _agent_metrics(row["agent_id"], row),
            },
        )
        state.bankrolls[name] = dollars(row["bankroll_after_round_cents"])
        attach_bankroll(state.stats[name], state.bankrolls[name])

    state.prize_pool = dollars(event["rollover_out_cents"])
    state.round_index = event["round"]
    state.history.append(record)
    if state.round_index >= state.config.n_rounds:
        state.finished = True
        record["final_summary"] = summary(
            list(state.stats.values()), state.stats.get("Dynamic")
        )
