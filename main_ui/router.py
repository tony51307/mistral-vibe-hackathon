"""Perturbation stability and pay-to-think decision logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from problems import answers_equivalent


DIFFICULTY_WEIGHT = {"easy": 0.2, "medium": 0.5, "hard": 0.85}


@dataclass
class RouterTrace:
    cheap_answer: str
    cheap_confidence: float
    cheap_reasoning: str
    perturbations: list[str]
    perturbed_answers: list[str]
    stability: str
    disagreement: float
    pay_to_think: bool
    reason: str
    deep_answer: str | None = None
    deep_confidence: float | None = None
    deep_reasoning: str | None = None
    changed_answer: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def disagreement_score(cheap: str, others: list[str]) -> float:
    if not others:
        return 0.0
    mismatches = sum(1 for a in others if not answers_equivalent(a, cheap))
    return mismatches / len(others)


def majority_answer(answers: list[str]) -> str:
    if not answers:
        return ""
    buckets: list[list[str]] = []
    for ans in answers:
        placed = False
        for bucket in buckets:
            if answers_equivalent(ans, bucket[0]):
                bucket.append(ans)
                placed = True
                break
        if not placed:
            buckets.append([ans])
    buckets.sort(key=len, reverse=True)
    return buckets[0][0]


def decide_pay_to_think(
    *,
    cheap_answer: str,
    cheap_confidence: float,
    perturbed_answers: list[str],
    prize: int,
    difficulty: str,
    bankroll: int,
    deep_cost: int,
    high_prize_threshold: int = 20,
) -> tuple[bool, str, float, str]:
    """Return (pay, reason, disagreement, stability)."""
    d = disagreement_score(cheap_answer, perturbed_answers)
    if d >= 0.5:
        stability = "LOW"
    elif d >= 0.25:
        stability = "MEDIUM"
    else:
        stability = "HIGH"

    can_afford = bankroll >= deep_cost
    high_disagreement = d >= 0.4
    low_conf_high_prize = cheap_confidence < 0.55 and prize >= high_prize_threshold
    hard_and_unsure = DIFFICULTY_WEIGHT.get(difficulty, 0.5) >= 0.8 and (
        d >= 0.25 or cheap_confidence < 0.6
    )

    if not can_afford:
        return False, "Cannot afford deep reasoning.", d, stability

    if high_disagreement or low_conf_high_prize or hard_and_unsure:
        bits = []
        if high_disagreement:
            bits.append("answer_disagreement is high")
        if low_conf_high_prize:
            bits.append("confidence is low and prize is high")
        if hard_and_unsure:
            bits.append("hard problem looks unstable")
        return True, "PAY_TO_THINK because " + "; ".join(bits) + ".", d, stability

    return False, "KEEP cheap answer: probes look stable enough.", d, stability


def normalize_model_output(data: dict[str, Any], fallback: str = "") -> tuple[str, float, str]:
    answer = str(data.get("answer", fallback) or fallback)
    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    reasoning = str(data.get("reasoning", "") or "")
    return answer, max(0.0, min(1.0, conf)), reasoning
