from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import random

from auto_thinking import AutoThinkingAdapter, RoutingContext, RoutingDecision
from economy import clamp_tier_to_bankroll
from mistral_client import MistralClient, extract_answer
from problems import Problem
from prompts import answer_prompt

DIFFICULTY_ACCURACY: dict[str, dict[str, float]] = {
    "easy": {"none": 0.90, "low": 0.92, "medium": 0.95, "high": 0.97, "xhigh": 0.99},
    "medium": {"none": 0.60, "low": 0.66, "medium": 0.76, "high": 0.85, "xhigh": 0.90},
    "hard": {"none": 0.32, "low": 0.42, "medium": 0.56, "high": 0.70, "xhigh": 0.78},
    "very hard": {
        "none": 0.16,
        "low": 0.24,
        "medium": 0.38,
        "high": 0.54,
        "xhigh": 0.64,
    },
}


WRONG_ANSWERS = ["0", "1", "2", "cannot determine", "false", "O(n^2)", "1/2"]
HIGH_STAKES_POT = 100


@dataclass
class AgentState:
    agent_id: str
    name: str
    policy: str
    bankroll: float
    eliminated: bool = False
    strategy_memory: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentTurn:
    agent_id: str
    public_message: str
    entry_paid: float
    show_hand: bool
    reasoning_tier: str
    reasoning_cost: float
    bankroll_after_reasoning: float
    submitted_answer: str
    routing_decision: RoutingDecision | None
    model_telemetry: dict


class AgentPolicy:
    def public_message(self, state: AgentState, category: str) -> str:
        msg = f"{category.title()} round. Watching the pot."
        return msg[:100]

    def choose_tier(
        self, state: AgentState, bankroll_after_entry: float, context: RoutingContext
    ) -> tuple[str, RoutingDecision | None]:
        raise NotImplementedError


class FastPolicy(AgentPolicy):
    def public_message(self, state: AgentState, category: str) -> str:
        return (
            f"{category.title()} feels like a gut-check. Conserving bankroll.".strip()[
                :100
            ]
        )

    def choose_tier(
        self, state: AgentState, bankroll_after_entry: float, context: RoutingContext
    ) -> tuple[str, RoutingDecision | None]:
        return clamp_tier_to_bankroll("none", bankroll_after_entry), None


class AlwaysThinkPolicy(AgentPolicy):
    def public_message(self, state: AgentState, category: str) -> str:
        return (
            f"{category.title()} is worth serious compute. I am buying depth.".strip()[
                :100
            ]
        )

    def choose_tier(
        self, state: AgentState, bankroll_after_entry: float, context: RoutingContext
    ) -> tuple[str, RoutingDecision | None]:
        # "Always think" means consistently buying non-cheap reasoning, not
        # necessarily the maximum tier every round. This keeps V1 economy
        # healthy while preserving the high-compute baseline.
        if context.pot >= HIGH_STAKES_POT or context.round_number % 12 == 0:
            target = "xhigh"
        elif context.round_number % 5 in {1, 2, 3}:
            target = "high"
        else:
            target = "medium"
        return clamp_tier_to_bankroll(target, bankroll_after_entry), None


class MediumControlPolicy(AgentPolicy):
    def public_message(self, state: AgentState, category: str) -> str:
        return f"{category.title()} round. Balanced spend, steady answer.".strip()[:100]

    def choose_tier(
        self, state: AgentState, bankroll_after_entry: float, context: RoutingContext
    ) -> tuple[str, RoutingDecision | None]:
        target = "medium" if context.round_number % 3 == 0 else "low"
        return clamp_tier_to_bankroll(target, bankroll_after_entry), None


class DynamicPolicy(AgentPolicy):
    def __init__(self, auto_thinking: AutoThinkingAdapter) -> None:
        self.auto_thinking = auto_thinking

    def public_message(self, state: AgentState, category: str) -> str:
        return f"{category.title()} signal first, then spend only if unstable.".strip()[
            :100
        ]

    def choose_tier(
        self, state: AgentState, bankroll_after_entry: float, context: RoutingContext
    ) -> tuple[str, RoutingDecision | None]:
        decision = self.auto_thinking.route(context)
        return clamp_tier_to_bankroll(
            decision.reasoning_tier, bankroll_after_entry
        ), decision


def default_agents(
    starting_bankroll: int, auto_thinking: AutoThinkingAdapter
) -> dict[str, AgentState]:
    return {
        "fast": AgentState("fast", "Fast Agent", "fast", starting_bankroll),
        "deep": AgentState(
            "deep", "Always Think Agent", "always_think", starting_bankroll
        ),
        "auto": AgentState("auto", "AutoThink Agent", "dynamic", starting_bankroll),
        "control": AgentState(
            "control", "Medium Control Agent", "medium", starting_bankroll
        ),
    }


def policy_for(agent: AgentState, auto_thinking: AutoThinkingAdapter) -> AgentPolicy:
    if agent.policy == "fast":
        return FastPolicy()
    if agent.policy == "always_think":
        return AlwaysThinkPolicy()
    if agent.policy == "dynamic":
        return DynamicPolicy(auto_thinking)
    return MediumControlPolicy()


def answer_problem(
    agent: AgentState,
    problem: Problem,
    tier: str,
    round_number: int,
    mistral_client: MistralClient | None = None,
    use_mistral: bool = False,
) -> tuple[str, dict]:
    if use_mistral and mistral_client and mistral_client.enabled:
        result = mistral_client.complete(answer_prompt(problem, tier), tier)
        return extract_answer(result.text), {
            "model": result.model,
            "provider": result.provider,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
            "api_reasoning_configuration": tier,
        }

    correct = _mock_correct(agent, problem, tier, round_number)
    answer = (
        problem.answer if correct else _mock_wrong_answer(agent, problem, round_number)
    )
    return answer, {
        "model": "offline-deterministic-simulator",
        "provider": "offline",
        "input_tokens": None,
        "output_tokens": None,
        "api_reasoning_configuration": tier,
    }


def _mock_correct(
    agent: AgentState, problem: Problem, tier: str, round_number: int
) -> bool:
    probability = DIFFICULTY_ACCURACY[problem.hidden_difficulty][tier]
    if agent.policy == "dynamic" and tier in {"high", "xhigh"}:
        probability = min(0.95, probability + 0.08)
    key = f"{agent.agent_id}:{problem.id}:{tier}:{round_number}"
    sample = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return sample < probability


def _mock_wrong_answer(agent: AgentState, problem: Problem, round_number: int) -> str:
    rng = random.Random(f"{agent.agent_id}:{problem.id}:{round_number}:wrong")
    choices = [
        answer for answer in WRONG_ANSWERS if answer not in problem.accepted_answers
    ]
    return rng.choice(choices)
