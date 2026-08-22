"""Prompts for cheap, perturbation, and deep reasoning calls."""

from __future__ import annotations


CHEAP_SYSTEM = (
    "You are a fast math solver. Answer quickly. "
    "Return JSON only with keys: answer (string), confidence (number 0-1), "
    "reasoning (one short sentence)."
)

DEEP_SYSTEM = (
    "You are a careful math reasoner. Work step by step before giving the final answer. "
    "Return JSON only with keys: answer (string), confidence (number 0-1), "
    "reasoning (concise multi-step explanation)."
)

PERTURB_GEN_SYSTEM = (
    "Rewrite a math problem into equivalent or near-equivalent variants that "
    "should have the same numerical answer. Change wording, units presentation, "
    "or surface numbers that cancel out, but keep the intended answer identical. "
    "Return JSON: {\"variants\": [string, string, string]}."
)

PERTURB_ANSWER_SYSTEM = CHEAP_SYSTEM


def cheap_user(question: str) -> str:
    return f"Solve this problem. Final answer should be a number or simplified fraction.\n\n{question}"


def deep_user(question: str) -> str:
    return (
        "Solve this problem carefully. Watch for common traps "
        "(with/without replacement, percent vs points, treating pairs as blocks).\n\n"
        f"{question}"
    )


def perturb_gen_user(question: str, n: int = 3) -> str:
    return (
        f"Create {n} perturbed restatements of this problem. "
        "Each restatement must have the same correct numerical answer.\n\n"
        f"{question}"
    )


def perturb_answer_user(question: str) -> str:
    return cheap_user(question)
