"""Two-phase rounds: sealed entrance, then private calculation cycles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents import AlwaysThinkAgent, CycleContext, DynamicAgent, FastAgent, PublicContext
from metrics import attach_bankroll, empty_stats, summary, update_after_round
from mistral_client import MistralClient
from problems import PRIZE_BY_DIFFICULTY, demo_schedule, is_correct


@dataclass
class GameConfig:
    start_bankroll: int = 100
    entrance_fee: int = 2
    n_rounds: int = 10
    n_perturbations: int = 4
    max_cycles: int = 3
    use_live_api: bool = False


@dataclass
class GameState:
    config: GameConfig
    problems: list[dict[str, Any]]
    round_index: int = 0
    prize_pool: int = 0
    bankrolls: dict[str, int] = field(default_factory=dict)
    stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    finished: bool = False


def _agents() -> list[Any]:
    return [FastAgent(), AlwaysThinkAgent(), DynamicAgent()]


def new_game(config: GameConfig) -> GameState:
    agents = _agents()
    names = [a.name for a in agents]
    return GameState(
        config=config,
        problems=demo_schedule(config.n_rounds),
        bankrolls={name: config.start_bankroll for name in names},
        stats={name: empty_stats(name, config.start_bankroll) for name in names},
    )


def play_round(state: GameState, client: MistralClient) -> dict[str, Any]:
    if state.finished or state.round_index >= len(state.problems):
        state.finished = True
        return {"finished": True}

    problem = state.problems[state.round_index]
    base_prize = PRIZE_BY_DIFFICULTY.get(problem["difficulty"], 15)
    rollover = state.prize_pool
    live = state.config.use_live_api and client.available
    fee = state.config.entrance_fee
    agents = _agents()
    for agent in agents:
        agent.reset_round()

    bankrolls_before = dict(state.bankrolls)
    announcement = {
        "round": state.round_index + 1,
        "category": problem["category"],
        "difficulty": problem["difficulty"],
        "question": problem["question"],
        "base_prize": base_prize,
        "rollover": rollover,
        "entrance_fee": fee,
        "public_bankrolls": bankrolls_before,
    }

    entries: dict[str, Any] = {}
    public_entries = []
    for agent in agents:
        ctx = PublicContext(
            problem=problem,
            base_prize=base_prize,
            rollover=rollover,
            prize=base_prize + rollover,
            entrance_fee=fee,
            bankroll=state.bankrolls[agent.name],
            public_bankrolls=bankrolls_before,
            entered=[],
            cycle_index=0,
            public_purchases=[],
            no_winner_last_cycle=False,
            use_live_api=live,
            client=client,
            n_perturbations=state.config.n_perturbations,
        )
        decision = agent.decide_entry(ctx)
        entries[agent.name] = decision
        if decision.enter:
            state.bankrolls[agent.name] -= fee
        public_entries.append(
            {
                "agent": agent.name,
                "decision": "ENTER" if decision.enter else "DECLINE",
                "entrance_fee": fee if decision.enter else 0,
            }
        )

    entered = [name for name, d in entries.items() if d.enter]
    total_prize = base_prize + rollover + fee * len(entered)
    bankrolls_after_entry = dict(state.bankrolls)
    announcement["prize"] = total_prize
    announcement["entered"] = entered

    spend = {name: (fee if name in entered else 0) for name in state.bankrolls}
    metrics_acc = {name: {} for name in state.bankrolls}
    submitted_any = {name: False for name in state.bankrolls}

    cycles: list[dict[str, Any]] = []
    winners: list[str] = []
    payouts: dict[str, int] = {name: 0 for name in state.bankrolls}
    payout_each = 0
    active = set(entered)
    public_purchases: list[dict[str, Any]] = []
    no_winner_last = False

    for cycle_i in range(1, state.config.max_cycles + 1):
        if not active:
            break

        public_actions = []
        dealer_actions = []
        submissions: dict[str, str] = {}
        thought_this_cycle = False

        for agent in agents:
            if agent.name not in active:
                continue
            ctx = CycleContext(
                problem=problem,
                base_prize=base_prize,
                rollover=rollover,
                prize=total_prize,
                entrance_fee=fee,
                bankroll=state.bankrolls[agent.name],
                public_bankrolls=dict(state.bankrolls),
                entered=list(entered),
                cycle_index=cycle_i,
                public_purchases=list(public_purchases),
                no_winner_last_cycle=no_winner_last,
                use_live_api=live,
                client=client,
                n_perturbations=state.config.n_perturbations,
                remaining_bankroll=state.bankrolls[agent.name],
            )
            act = agent.decide_cycle(ctx)
            if act.action == "THINK":
                if act.amount > state.bankrolls[agent.name]:
                    act.action = "EXIT"
                    act.amount = 0
                    act.answer = ""
                else:
                    state.bankrolls[agent.name] -= act.amount
                    spend[agent.name] += act.amount
                    submissions[agent.name] = act.answer
                    submitted_any[agent.name] = True
                    thought_this_cycle = True
                    public_purchases.append(
                        {"cycle": cycle_i, "agent": agent.name, "think": act.amount}
                    )
            if act.action == "EXIT":
                active.discard(agent.name)

            _merge_metrics(metrics_acc[agent.name], act.metrics)
            public_actions.append(
                {
                    "agent": agent.name,
                    "action": act.action,
                    "think_credits": act.amount if act.action == "THINK" else 0,
                    "policy": act.public.get("policy"),
                }
            )
            dealer_actions.append(
                {
                    "agent": agent.name,
                    "action": act.action,
                    "think_credits": act.amount,
                    "answer": act.answer,
                    "dealer": act.dealer,
                    "metrics": act.metrics,
                }
            )

        cycle_winners = [name for name, ans in submissions.items() if is_correct(ans, problem)]
        public_cycle: dict[str, Any] = {
            "cycle": cycle_i,
            "actions": public_actions,
            "submitted_count": len(submissions),
            "winner_announced": bool(cycle_winners),
            "winners": cycle_winners,
        }
        if cycle_winners:
            public_cycle["dealer_announcement"] = (
                f"Winning cycle. Prize split equally among: {', '.join(cycle_winners)}."
            )
        else:
            public_cycle["dealer_announcement"] = (
                "No winner this cycle. Incorrect answers are not revealed. "
                "A new solving cycle may begin."
            )

        cycles.append({"public": public_cycle, "dealer": dealer_actions})

        if cycle_winners:
            winners = cycle_winners
            payout_each = total_prize // len(winners)
            remainder = total_prize % len(winners)
            for i, name in enumerate(winners):
                pay = payout_each + (remainder if i == 0 else 0)
                payouts[name] = pay
                state.bankrolls[name] += pay
            state.prize_pool = 0
            break

        no_winner_last = True
        if not thought_this_cycle:
            break

    if not winners:
        state.prize_pool = total_prize

    for name in state.bankrolls:
        entered_round = name in entered
        update_after_round(
            state.stats[name],
            {
                "decision": "ENTER" if entered_round else "DECLINE",
                "spent": spend[name],
                "correct": name in winners,
                "submitted": submitted_any[name],
                "payout": payouts[name],
                "metrics": metrics_acc[name],
            },
        )
        attach_bankroll(state.stats[name], state.bankrolls[name])

    record = {
        "finished": False,
        "round": state.round_index + 1,
        "announcement": announcement,
        "problem": {
            "id": problem["id"],
            "question": problem["question"],
            "answer": problem["answer"],
            "explanation": problem["explanation"],
            "difficulty": problem["difficulty"],
            "category": problem["category"],
        },
        "phase1": {
            "entries": public_entries,
            "entered": entered,
            "prize_pool": total_prize,
            "public_bankrolls_after_entry": bankrolls_after_entry,
        },
        "cycles": cycles,
        "winners": winners,
        "payouts": payouts,
        "payout_each": payout_each,
        "prize": total_prize,
        "rollover": state.prize_pool if not winners else 0,
        "bankrolls": dict(state.bankrolls),
        "dealer_entries": {name: entries[name].reason for name in entries},
    }

    state.history.append(record)
    state.round_index += 1
    if state.round_index >= len(state.problems):
        state.finished = True
        record["final_summary"] = summary(list(state.stats.values()), state.stats.get("Dynamic"))
    return record


def _merge_metrics(acc: dict[str, Any], extra: dict[str, Any]) -> None:
    for key in ("cheap_calls", "perturbation_calls", "deep_calls"):
        acc[key] = acc.get(key, 0) + extra.get(key, 0)
    if extra.get("deep_triggered"):
        acc["deep_triggered"] = True
    if extra.get("changed_answer"):
        acc["changed_answer"] = True
    if extra.get("useful_revision"):
        acc["useful_revision"] = extra["useful_revision"]
