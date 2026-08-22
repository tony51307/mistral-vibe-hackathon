from __future__ import annotations

from pydantic import ValidationError
import pytest

from vibe.core.reasoning import ProbeDecision, ProbePerspective
from vibe.core.reasoning.router import (
    build_probe_messages,
    is_trivial_request,
    route_probe_decisions,
)


def _decision(
    action: str = "inspect", targets: list[str] | None = None, risk: str = "low"
) -> ProbeDecision:
    return ProbeDecision.model_validate({
        "action": action,
        "targets": targets or ["agent_loop"],
        "risk": risk,
        "confidence": 0.8,
    })


def test_stable_probes_select_low_thinking() -> None:
    decision = route_probe_decisions([_decision(), _decision()])

    assert decision.level == "low"
    assert decision.stability == 1
    assert decision.reason == "stable"


def test_action_disagreement_selects_high_thinking() -> None:
    decision = route_probe_decisions([_decision(), _decision(action="edit")])

    assert decision.level == "high"
    assert decision.stability == 0.5
    assert decision.reason == "disagreement"


def test_high_risk_selects_high_thinking_even_when_stable() -> None:
    decision = route_probe_decisions([_decision(), _decision(risk="high")])

    assert decision.level == "high"
    assert decision.reason == "high_risk"


def test_configured_bounds_clamp_routed_level() -> None:
    stable = route_probe_decisions([_decision()], minimum="medium", maximum="high")
    unstable = route_probe_decisions(
        [_decision(), _decision(action="edit")], minimum="low", maximum="medium"
    )

    assert stable.level == "medium"
    assert unstable.level == "medium"


def test_semantically_overlapping_targets_are_stable() -> None:
    decision = route_probe_decisions([
        _decision(targets=["README"]),
        _decision(targets=["README heading"]),
    ])

    assert decision.level == "low"
    assert decision.stability == 1


@pytest.mark.parametrize(
    "prompt",
    [
        "Answer only with READY.",
        "Correct a typo in the README heading.",
        "Fix documentation spelling.",
    ],
)
def test_trivial_requests_use_fast_path(prompt: str) -> None:
    assert is_trivial_request(prompt)


@pytest.mark.parametrize(
    "prompt",
    [
        "Delete a production database migration.",
        "Change authentication documentation.",
        "Fix a README typo. " * 30,
    ],
)
def test_risky_or_large_requests_do_not_use_fast_path(prompt: str) -> None:
    assert not is_trivial_request(prompt)


def test_probe_response_extracts_json_from_code_fence() -> None:
    decision = ProbeDecision.parse_response(
        '```json\n{"action":"inspect","targets":[],"risk":"low","confidence":0.7}\n```'
    )

    assert decision.action == "inspect"


def test_probe_response_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ProbeDecision.parse_response(
            '{"action":"inspect","targets":[],"risk":"low",'
            '"confidence":0.7,"answer":"secret"}'
        )


def test_probe_perspectives_preserve_original_request() -> None:
    request = "Delete neither file; inspect both."

    messages = build_probe_messages(request, ProbePerspective.CRITIC)

    assert request in (messages[-1].content or "")
    assert "Do not change any facts or constraints" in (messages[0].content or "")
