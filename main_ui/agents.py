"""Fast, Always Think, and Dynamic Pay-to-Think agents.

Phase 1: ENTER or DECLINE. Same fixed entrance fee for everyone.
Phase 2: THINK(amount), PASS, or EXIT. Reasoning stays private.
Agents never receive another agent's answer, confidence, probes, or traces.
They only see the public announcement, public bankrolls, who entered,
and how many thinking credits others bought.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from mistral_client import CHEAP_COST, DEEP_COST, DYNAMIC_COST, PERTURB_COST, MistralClient
from problems import answers_equivalent
import prompts
from router import RouterTrace, decide_pay_to_think, normalize_model_output


class Agent(Protocol):
    name: str
    style: str

    def reset_round(self) -> None: ...
    def decide_entry(self, ctx: "PublicContext") -> "EntryDecision": ...
    def decide_cycle(self, ctx: "CycleContext") -> "CycleAction": ...


@dataclass
class PublicContext:
    problem: dict[str, Any]
    base_prize: int
    rollover: int
    prize: int
    entrance_fee: int
    bankroll: int
    public_bankrolls: dict[str, int]
    entered: list[str]
    cycle_index: int
    public_purchases: list[dict[str, Any]]
    no_winner_last_cycle: bool
    use_live_api: bool
    client: MistralClient
    n_perturbations: int = 4


@dataclass
class CycleContext(PublicContext):
    remaining_bankroll: int = 0


@dataclass
class EntryDecision:
    enter: bool
    reason: str


@dataclass
class CycleAction:
    action: str  # THINK | PASS | EXIT
    amount: int = 0
    answer: str = ""
    public: dict[str, Any] = field(default_factory=dict)
    dealer: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


class FastAgent:
    name = "Fast"
    style = "Never buys deeper thinking. One cheap call."

    def __init__(self) -> None:
        self._tried = False

    def reset_round(self) -> None:
        self._tried = False

    def decide_entry(self, ctx: PublicContext) -> EntryDecision:
        if ctx.bankroll < ctx.entrance_fee + CHEAP_COST:
            return EntryDecision(False, "Cannot afford entrance fee plus one cheap call.")
        return EntryDecision(True, "Enter. Will buy one cheap call.")

    def decide_cycle(self, ctx: CycleContext) -> CycleAction:
        if self._tried:
            return CycleAction(
                action="EXIT",
                public={"policy": "cheap-only"},
                dealer={"reason": "Already used the cheap pass. Will not buy deeper thinking."},
            )
        if ctx.remaining_bankroll < CHEAP_COST:
            return CycleAction(action="EXIT", dealer={"reason": "Cannot afford a cheap call."})

        answer, conf, reasoning = _cheap_solve(ctx)
        self._tried = True
        return CycleAction(
            action="THINK",
            amount=CHEAP_COST,
            answer=answer,
            public={"policy": "cheap-only"},
            dealer={
                "calls": ["cheap"],
                "reasoning": reasoning,
                "confidence": conf,
                "note": "Private cheap pass. Hidden from other agents.",
            },
            metrics={"cheap_calls": 1},
        )


class AlwaysThinkAgent:
    name = "Always Think"
    style = "Always spends a fixed deep-reasoning budget."

    def __init__(self) -> None:
        self._tried = False

    def reset_round(self) -> None:
        self._tried = False

    def decide_entry(self, ctx: PublicContext) -> EntryDecision:
        if ctx.bankroll < ctx.entrance_fee + DEEP_COST:
            return EntryDecision(False, "Cannot afford entrance fee plus deep reasoning.")
        return EntryDecision(True, "Enter. Will buy the fixed deep budget.")

    def decide_cycle(self, ctx: CycleContext) -> CycleAction:
        if self._tried:
            return CycleAction(
                action="EXIT",
                public={"policy": "always-deep"},
                dealer={"reason": "Already used the deep pass."},
            )
        if ctx.remaining_bankroll < DEEP_COST:
            return CycleAction(action="EXIT", dealer={"reason": "Cannot afford deep reasoning."})

        answer, conf, reasoning = _deep_solve(ctx)
        self._tried = True
        return CycleAction(
            action="THINK",
            amount=DEEP_COST,
            answer=answer,
            public={"policy": "always-deep"},
            dealer={
                "calls": ["deep"],
                "reasoning": reasoning,
                "confidence": conf,
                "note": "Private deep chain. Hidden from other agents.",
            },
            metrics={"deep_calls": 1},
        )


class DynamicAgent:
    name = "Dynamic"
    style = "Perturbation-guided pay-to-think router."

    def __init__(self) -> None:
        self._probed = False
        self._deeps = False
        self._cheap_answer = ""
        self._want_deep = False
        self._stability = ""
        self._trace: dict[str, Any] | None = None

    def reset_round(self) -> None:
        self._probed = False
        self._deeps = False
        self._cheap_answer = ""
        self._want_deep = False
        self._stability = ""
        self._trace = None

    def decide_entry(self, ctx: PublicContext) -> EntryDecision:
        needed = ctx.entrance_fee + CHEAP_COST
        if ctx.bankroll < needed:
            return EntryDecision(False, "Cannot afford entrance fee plus a cheap pass.")
        return EntryDecision(True, "Enter. Will probe, then maybe buy deep reasoning.")

    def decide_cycle(self, ctx: CycleContext) -> CycleAction:
        if not self._probed:
            if ctx.remaining_bankroll < CHEAP_COST:
                return CycleAction(action="EXIT", dealer={"reason": "Cannot afford probes."})
            return self._cycle_probes(ctx)

        if self._deeps:
            return CycleAction(
                action="EXIT",
                public={"policy": "pay-to-think", "paid_to_think": True},
                dealer={"reason": "Already used deep reasoning.", "trace": self._trace},
            )

        if ctx.no_winner_last_cycle:
            self._want_deep = True

        if not self._want_deep:
            return CycleAction(
                action="EXIT",
                public={"policy": "pay-to-think", "paid_to_think": False},
                dealer={
                    "reason": "Probes looked stable; not buying deep reasoning.",
                    "trace": self._trace,
                },
            )

        extra = max(0, DYNAMIC_COST - CHEAP_COST)
        if ctx.remaining_bankroll < extra:
            return CycleAction(
                action="EXIT",
                public={"policy": "pay-to-think", "paid_to_think": False},
                dealer={"reason": "Wanted deep reasoning but cannot afford it.", "trace": self._trace},
            )

        return self._cycle_deep(ctx)

    def _cycle_probes(self, ctx: CycleContext) -> CycleAction:
        cheap_answer, cheap_conf, cheap_reason = _cheap_solve(ctx)
        variants, pert_answers, pert_details = _run_probes(ctx)
        remaining = ctx.remaining_bankroll - CHEAP_COST
        pay, reason, disagreement, stability = decide_pay_to_think(
            cheap_answer=cheap_answer,
            cheap_confidence=cheap_conf,
            perturbed_answers=pert_answers,
            prize=ctx.prize,
            difficulty=ctx.problem["difficulty"],
            bankroll=remaining,
            deep_cost=DYNAMIC_COST - CHEAP_COST,
        )
        self._probed = True
        self._cheap_answer = cheap_answer
        self._want_deep = pay
        self._stability = stability
        trace = RouterTrace(
            cheap_answer=cheap_answer,
            cheap_confidence=cheap_conf,
            cheap_reasoning=cheap_reason,
            perturbations=variants,
            perturbed_answers=pert_answers,
            stability=stability,
            disagreement=disagreement,
            pay_to_think=pay,
            reason=reason,
        )
        self._trace = trace.__dict__

        final = cheap_answer
        amount = CHEAP_COST
        changed = False
        useful = None
        deep_calls = 0
        if pay and ctx.remaining_bankroll >= DYNAMIC_COST:
            deep_answer, deep_conf, deep_reason = _deep_solve(ctx)
            self._deeps = True
            final = deep_answer
            amount = DYNAMIC_COST
            deep_calls = 1
            changed = not answers_equivalent(cheap_answer, deep_answer)
            if changed and answers_equivalent(deep_answer, ctx.problem["answer"]) and not answers_equivalent(
                cheap_answer, ctx.problem["answer"]
            ):
                useful = {
                    "problem_id": ctx.problem["id"],
                    "cheap": cheap_answer,
                    "deep": deep_answer,
                    "stability": stability,
                }
            self._trace.update(
                {
                    "deep_answer": deep_answer,
                    "deep_confidence": deep_conf,
                    "deep_reasoning": deep_reason,
                    "changed_answer": changed,
                }
            )

        return CycleAction(
            action="THINK",
            amount=amount,
            answer=final,
            public={
                "policy": "pay-to-think",
                "paid_to_think": bool(deep_calls),
                "phase": "deep" if deep_calls else "probes",
            },
            dealer={
                "trace": self._trace,
                "probe_details": pert_details,
                "note": "Dealer-only router trace. Other agents cannot see probes or answers.",
            },
            metrics={
                "cheap_calls": 1,
                "perturbation_calls": ctx.n_perturbations,
                "deep_calls": deep_calls,
                "deep_triggered": pay,
                "changed_answer": changed,
                "useful_revision": useful,
            },
        )

    def _cycle_deep(self, ctx: CycleContext) -> CycleAction:
        deep_answer, deep_conf, deep_reason = _deep_solve(ctx)
        self._deeps = True
        changed = not answers_equivalent(self._cheap_answer, deep_answer)
        useful = None
        if changed and answers_equivalent(deep_answer, ctx.problem["answer"]) and not answers_equivalent(
            self._cheap_answer, ctx.problem["answer"]
        ):
            useful = {
                "problem_id": ctx.problem["id"],
                "cheap": self._cheap_answer,
                "deep": deep_answer,
                "stability": self._stability,
            }
        if self._trace:
            self._trace.update(
                {
                    "pay_to_think": True,
                    "deep_answer": deep_answer,
                    "deep_confidence": deep_conf,
                    "deep_reasoning": deep_reason,
                    "changed_answer": changed,
                }
            )
        return CycleAction(
            action="THINK",
            amount=max(0, DYNAMIC_COST - CHEAP_COST),
            answer=deep_answer,
            public={"policy": "pay-to-think", "paid_to_think": True, "phase": "deep"},
            dealer={
                "trace": self._trace,
                "note": "Private deep revision after instability or a failed cycle.",
            },
            metrics={
                "deep_calls": 1,
                "deep_triggered": True,
                "changed_answer": changed,
                "useful_revision": useful,
            },
        )


def _cheap_solve(ctx: PublicContext) -> tuple[str, float, str]:
    if not ctx.use_live_api:
        return ctx.problem.get("cheap_stub", ctx.problem["answer"]), 0.45, "Seeded cheap pass."
    data = ctx.client.chat_json(
        system=prompts.CHEAP_SYSTEM,
        user=prompts.cheap_user(ctx.problem["question"]),
        strong=False,
    )
    return normalize_model_output(data)


def _deep_solve(ctx: PublicContext) -> tuple[str, float, str]:
    if not ctx.use_live_api:
        return ctx.problem.get("deep_stub", ctx.problem["answer"]), 0.9, "Seeded deep pass."
    data = ctx.client.chat_json(
        system=prompts.DEEP_SYSTEM,
        user=prompts.deep_user(ctx.problem["question"]),
        strong=True,
        temperature=0.1,
    )
    return normalize_model_output(data)


def _run_probes(ctx: PublicContext) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    n = ctx.n_perturbations
    if not ctx.use_live_api:
        stubs = list(ctx.problem.get("perturbation_stubs") or [])
        while len(stubs) < n:
            stubs.append(ctx.problem.get("cheap_stub", ctx.problem["answer"]))
        variants = [f"Seeded restatement {i + 1} of: {ctx.problem['question']}" for i in range(n)]
        details = [
            {"variant": variants[i], "answer": stubs[i], "confidence": 0.5} for i in range(n)
        ]
        return variants, stubs[:n], details

    gen = ctx.client.chat_json(
        system=prompts.PERTURB_GEN_SYSTEM,
        user=prompts.perturb_gen_user(ctx.problem["question"], n),
        strong=False,
        temperature=0.7,
    )
    variants = [str(v) for v in (gen.get("variants") or [])][:n]
    while len(variants) < n:
        variants.append(ctx.problem["question"])

    answers: list[str] = []
    details: list[dict[str, Any]] = []
    for variant in variants:
        data = ctx.client.chat_json(
            system=prompts.PERTURB_ANSWER_SYSTEM,
            user=prompts.perturb_answer_user(variant),
            strong=False,
        )
        ans, conf, reason = normalize_model_output(data)
        answers.append(ans)
        details.append(
            {"variant": variant, "answer": ans, "confidence": conf, "reasoning": reason}
        )
    return variants, answers, details
