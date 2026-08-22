from __future__ import annotations

from enum import StrEnum, auto
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vibe.config_values import ThinkingLevel
from vibe.core.types import LLMMessage, Role


class ProbePerspective(StrEnum):
    DECISION_FIRST = auto()
    CRITIC = auto()


class ProbeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    targets: list[str] = Field(default_factory=list)
    risk: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0, le=1)

    @classmethod
    def parse_response(cls, content: str) -> ProbeDecision:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if match is None:
            raise ValueError("Reasoning probe did not return JSON")
        return cls.model_validate(json.loads(match.group()))


class ReasoningRoutingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: ThinkingLevel
    stability: float = Field(ge=0, le=1)
    reason: Literal["fast_path", "stable", "disagreement", "high_risk", "probe_failed"]


_PROBE_SYSTEM = """You are a cheap decision-stability probe for a coding agent.
Do not solve the task or use tools. Do not change any facts or constraints.
Return only JSON with this exact shape:
{"action":"inspect|edit|run|answer|plan|ask", "targets":["short names"],
 "risk":"low|medium|high", "confidence":0.0}
Keep targets short and include at most three."""

_FAST_PATH_PATTERNS = (
    r"\banswer only\b",
    r"\b(readme|documentation|docs?)\b.*\b(typo|spelling|heading|formatting)\b",
    r"\b(typo|spelling|heading|formatting)\b.*\b(readme|documentation|docs?)\b",
)
_HIGH_RISK_PATTERNS = (
    r"\b(log|print|echo|expose|publish)\b.{0,80}\b(api[ -]?tokens?|credentials?|secrets?)\b",
    r"\b(api[ -]?tokens?|credentials?|secrets?)\b.{0,80}\b(log|print|echo|expose|publish)\b",
    r"\bauthori[sz]ation\b.{0,100}\b(server|backend)\b.{0,100}\b(client|frontend|browser)\b",
    r"\b(remov(?:e|ing)|delet(?:e|ing))\b.{0,100}\b(public (api|function)|minor release)\b",
    r"\buser[- ]controlled\b.{0,100}\b(privileged )?(shell )?command\b",
    r"\b(async|concurren\w*)\b.{0,100}\b(parallel|race|synchroni[sz]|arbitrary sleep)\b",
)
_HIGH_CONSEQUENCE_TERMS = re.compile(
    r"\b(auth(?:entication|orization)?|credential|database|delete|deploy|migration|"
    r"permission|production|release|secret|security)\b",
    flags=re.IGNORECASE,
)
_TARGET_STOP_WORDS = {"a", "and", "boundary", "file", "module", "the"}
_TARGET_SYNONYMS = {"configuration": "config", "documentation": "docs"}
_FAST_PATH_MAX_CHARS = 300


def is_trivial_request(request: str) -> bool:
    if len(request) > _FAST_PATH_MAX_CHARS or _HIGH_CONSEQUENCE_TERMS.search(request):
        return False
    return any(
        re.search(pattern, request, flags=re.IGNORECASE)
        for pattern in _FAST_PATH_PATTERNS
    )


def is_high_risk_request(request: str) -> bool:
    return any(
        re.search(pattern, request, flags=re.IGNORECASE | re.DOTALL)
        for pattern in _HIGH_RISK_PATTERNS
    )


def build_probe_messages(
    request: str, perspective: ProbePerspective
) -> list[LLMMessage]:
    instruction = {
        ProbePerspective.DECISION_FIRST: "Choose the safest effective next action.",
        ProbePerspective.CRITIC: (
            "Identify how the obvious approach could fail, then choose the safest "
            "effective next action."
        ),
    }[perspective]
    return [
        LLMMessage(role=Role.system, content=_PROBE_SYSTEM),
        LLMMessage(role=Role.user, content=f"{instruction}\n\nTask:\n{request}"),
    ]


def route_probe_decisions(
    decisions: list[ProbeDecision],
    *,
    minimum: ThinkingLevel = "low",
    maximum: ThinkingLevel = "high",
) -> ReasoningRoutingDecision:
    if not decisions:
        raise ValueError("At least one probe decision is required")
    baseline = decisions[0]
    critic = decisions[-1]
    action_agrees = baseline.action.casefold() == critic.action.casefold()
    targets_a = _target_terms(baseline.targets)
    targets_b = _target_terms(critic.targets)
    target_agrees = not targets_a or not targets_b or bool(targets_a & targets_b)
    risk_high = "high" in {baseline.risk, critic.risk}
    stability = (float(action_agrees) + float(target_agrees)) / 2
    if risk_high:
        level = clamp_thinking_level("high", minimum=minimum, maximum=maximum)
        return ReasoningRoutingDecision(
            level=level, stability=stability, reason="high_risk"
        )
    if stability < 1:
        level = clamp_thinking_level("high", minimum=minimum, maximum=maximum)
        return ReasoningRoutingDecision(
            level=level, stability=stability, reason="disagreement"
        )
    level = clamp_thinking_level("low", minimum=minimum, maximum=maximum)
    return ReasoningRoutingDecision(level=level, stability=1, reason="stable")


def _target_terms(targets: list[str]) -> set[str]:
    terms = {
        _TARGET_SYNONYMS.get(term) or term
        for target in targets
        for term in re.findall(r"[a-z0-9]+", target.casefold())
    }
    return terms - _TARGET_STOP_WORDS


def clamp_thinking_level(
    level: ThinkingLevel, *, minimum: ThinkingLevel, maximum: ThinkingLevel
) -> ThinkingLevel:
    levels: tuple[ThinkingLevel, ...] = ("off", "low", "medium", "high", "max")
    index = min(max(levels.index(level), levels.index(minimum)), levels.index(maximum))
    return levels[index]
