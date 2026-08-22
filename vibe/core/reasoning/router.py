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
    context: str | None = None


_PROBE_SYSTEM = """You are a cheap decision-stability probe for a coding agent.
Do not solve the task or use tools. Do not change any facts or constraints.
Risk means the reasoning effort required for a materially correct answer, not safety.
Use low only for direct recall or a single mechanical step with no edge cases. Use
medium for multi-step calculations, interacting constraints, or ambiguity. Use high
for probability, proofs, optimization, boundary cases, or conclusions whose subtle
errors are hard to detect. Brief requested output does not make a task easy: ignore
phrases such as "answer only" when assigning risk.
Return only JSON with this exact shape:
{"action":"inspect|edit|run|answer|plan|ask", "targets":["short names"],
 "risk":"low|medium|high", "confidence":0.0}
Keep targets short and include at most three."""

_FAST_PATH_PATTERNS = (
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
_HIGH_REASONING_TERMS = re.compile(
    r"\b(at least|at most|counterexample|exactly|optimi[sz]\w*|paradox\w*|"
    r"probabilit\w*|prove|proof|without replacement)\b",
    flags=re.IGNORECASE,
)
_QUANTITATIVE_TERMS = re.compile(
    r"\b(acceleration|complexity|divisors?|edges?|energy|factor|force|graph|"
    r"percent|solve|speed|velocity|weight)\b|%|\^|\d\s*[+*/=-]",
    flags=re.IGNORECASE,
)
_LOGICAL_TERMS = re.compile(
    r"\b(all|and|false|if|implies|neither|then|true)\b", flags=re.IGNORECASE
)
_TARGET_STOP_WORDS = {"a", "and", "boundary", "file", "module", "the"}
_TARGET_SYNONYMS = {"configuration": "config", "documentation": "docs"}
_FAST_PATH_MAX_CHARS = 300
_CONFIDENT_PROBE_THRESHOLD = 0.8
_MULTI_STEP_NUMBER_COUNT = 2
_MULTI_STEP_LOGIC_TERM_COUNT = 3


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


def is_high_consequence_request(request: str) -> bool:
    return _HIGH_CONSEQUENCE_TERMS.search(request) is not None


def infer_reasoning_floor(request: str) -> ThinkingLevel:
    if _HIGH_REASONING_TERMS.search(request):
        return "high"
    number_count = len(re.findall(r"(?<!\w)\d+(?:\.\d+)?", request))
    if number_count >= _MULTI_STEP_NUMBER_COUNT and _QUANTITATIVE_TERMS.search(request):
        return "medium"
    if len(_LOGICAL_TERMS.findall(request)) >= _MULTI_STEP_LOGIC_TERM_COUNT:
        return "medium"
    return "low"


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
    high_consequence: bool = False,
) -> ReasoningRoutingDecision:
    if not decisions:
        raise ValueError("At least one probe decision is required")
    baseline = decisions[0]
    critic = decisions[-1]
    if len(decisions) == 1:
        level: ThinkingLevel = (
            "medium"
            if baseline.risk == "low"
            and baseline.confidence < _CONFIDENT_PROBE_THRESHOLD
            else baseline.risk
        )
        return ReasoningRoutingDecision(
            level=clamp_thinking_level(level, minimum=minimum, maximum=maximum),
            stability=baseline.confidence,
            reason=(
                "high_risk"
                if baseline.risk == "high"
                else "disagreement"
                if level == "medium"
                else "stable"
            ),
        )
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
    if min(baseline.confidence, critic.confidence) < _CONFIDENT_PROBE_THRESHOLD:
        selected = "high" if high_consequence else "medium"
        return ReasoningRoutingDecision(
            level=clamp_thinking_level(selected, minimum=minimum, maximum=maximum),
            stability=min(baseline.confidence, critic.confidence),
            reason="high_risk" if high_consequence else "disagreement",
        )
    if stability < 1:
        selected: ThinkingLevel = "high" if high_consequence else "medium"
        level = clamp_thinking_level(selected, minimum=minimum, maximum=maximum)
        return ReasoningRoutingDecision(
            level=level,
            stability=stability,
            reason="high_risk" if high_consequence else "disagreement",
        )
    medium_risk = "medium" in {baseline.risk, critic.risk}
    selected = (
        "high"
        if high_consequence and medium_risk
        else "medium"
        if medium_risk
        else "low"
    )
    level = clamp_thinking_level(selected, minimum=minimum, maximum=maximum)
    return ReasoningRoutingDecision(
        level=level, stability=1, reason="high_risk" if selected == "high" else "stable"
    )


def should_run_critic(decision: ProbeDecision, request: str) -> bool:
    return decision.risk != "high" and (
        decision.confidence < _CONFIDENT_PROBE_THRESHOLD
        or is_high_consequence_request(request)
    )


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
