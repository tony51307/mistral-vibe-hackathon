from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vibe.config_values import ThinkingLevel
from vibe.core.reasoning.router import (
    ReasoningRoutingDecision,
    clamp_thinking_level,
    is_high_consequence_request,
)
from vibe.core.types import LLMMessage, Role


class CandidateAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: str
    assumptions: list[str] = Field(default_factory=list, max_length=3)
    risk: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0, le=1)
    cheaply_verifiable: bool

    @field_validator("candidate", mode="before")
    @classmethod
    def normalize_candidate(cls, value: object) -> str:
        return str(value)

    @classmethod
    def parse_response(cls, content: str) -> CandidateAssessment:
        payload = _extract_json(content)
        if payload is not None:
            return cls.model_validate(payload)
        return cls(
            candidate=content.strip(),
            assumptions=[],
            risk="medium",
            confidence=0,
            cheaply_verifiable=False,
        )


class CandidateCritique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_issue: bool
    severity: Literal["none", "low", "medium", "high"]
    critique: str
    confidence: float = Field(ge=0, le=1)

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_empty_severity(cls, value: object) -> object:
        return "none" if value == "" else value

    @model_validator(mode="after")
    def validate_material_severity(self) -> CandidateCritique:
        if self.material_issue and self.severity == "none":
            self.severity = "medium"
        return self

    @classmethod
    def parse_response(cls, content: str) -> CandidateCritique:
        payload = _extract_json(content)
        if payload is not None:
            return cls.model_validate(payload)
        return cls(
            material_issue=True,
            severity="medium",
            critique=content.strip() or "Critique output was unavailable",
            confidence=0,
        )


_CANDIDATE_SYSTEM = """You are a low-cost first-pass solver for a coding agent.
Produce a concrete candidate that is useful to the final agent, not a routing label.
Do not use tools. Return only JSON with this exact shape:
{"candidate":"concise answer or approach", "assumptions":["at most three"],
 "risk":"low|medium|high", "confidence":0.0, "cheaply_verifiable":true}
Confidence means probability the candidate is materially correct."""

_CRITIC_SYSTEM = """You are a low-cost verifier deciding whether more reasoning has value.
Evaluate the candidate against the original task. Identify only concrete defects that
could materially change the result. Do not reward verbosity or speculate vaguely.
Return only JSON with this exact shape:
{"material_issue":true, "severity":"none|low|medium|high",
 "critique":"specific defect or empty string", "confidence":0.0}"""


def build_candidate_messages(request: str) -> list[LLMMessage]:
    return [
        LLMMessage(role=Role.system, content=_CANDIDATE_SYSTEM),
        LLMMessage(role=Role.user, content=request),
    ]


def build_critic_messages(
    request: str, candidate: CandidateAssessment
) -> list[LLMMessage]:
    payload = candidate.model_dump_json()
    return [
        LLMMessage(role=Role.system, content=_CRITIC_SYSTEM),
        LLMMessage(
            role=Role.user,
            content=f"Original task:\n{request}\n\nLow-cost candidate:\n{payload}",
        ),
    ]


def route_candidate(
    request: str,
    candidate: CandidateAssessment,
    critique: CandidateCritique | None,
    *,
    minimum: ThinkingLevel = "low",
    maximum: ThinkingLevel = "high",
) -> ReasoningRoutingDecision:
    selected: ThinkingLevel = candidate.risk
    reason: Literal["stable", "disagreement", "high_risk"] = "stable"
    stability = candidate.confidence
    if critique is not None:
        stability = (
            1 - critique.confidence if critique.material_issue else critique.confidence
        )
        if critique.material_issue:
            selected = "medium" if critique.severity == "none" else critique.severity
            reason = "disagreement"
    if is_high_consequence_request(request) and selected == "medium":
        selected = "high"
        reason = "high_risk"
    if selected == "high":
        reason = "high_risk"
    return ReasoningRoutingDecision(
        level=clamp_thinking_level(selected, minimum=minimum, maximum=maximum),
        stability=stability,
        reason=reason,
        context=render_candidate_context(candidate, critique),
    )


def render_candidate_context(
    candidate: CandidateAssessment, critique: CandidateCritique | None
) -> str:
    critique_text = critique.model_dump_json() if critique is not None else "not run"
    return (
        "<auto_thinking_evidence>\n"
        "A low-cost candidate and optional critique were produced before this turn. "
        "Use them as preliminary evidence, independently verify them, and do not "
        "mention the router to the user.\n"
        f"Candidate: {candidate.model_dump_json()}\n"
        f"Critique: {critique_text}\n"
        "</auto_thinking_evidence>"
    )


def _extract_json(content: str) -> object | None:
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if match is None:
        return None
    return json.loads(match.group())
