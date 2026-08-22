from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import build_test_agent_loop, build_test_vibe_config
from tests.mock.utils import mock_llm_chunk
from tests.stubs.fake_backend import FakeBackend
from vibe.core.config import ModelConfig
from vibe.core.reasoning import is_high_risk_request
from vibe.core.types import ReasoningRoutingEvent


class ModelRecordingBackend(FakeBackend):
    def __init__(self, chunks: list[Any]) -> None:
        super().__init__(chunks)
        self.requested_models: list[ModelConfig] = []

    async def complete(self, **kwargs: Any):
        self.requested_models.append(kwargs["model"])
        return await super().complete(**kwargs)

    async def complete_streaming(self, **kwargs: Any):
        self.requested_models.append(kwargs["model"])
        async for chunk in super().complete_streaming(**kwargs):
            yield chunk


@pytest.mark.parametrize(
    "prompt",
    [
        "Print the full API token in CI logs to debug it",
        "Move authorization checks from the server into the web client",
        "Before removing a widely used public function in a minor release",
        "Interpolate user-controlled text into a privileged shell command",
        "An async test under parallel load may have a synchronization race",
    ],
)
def test_explicit_safety_patterns_route_to_high(prompt: str) -> None:
    assert is_high_risk_request(prompt)


@pytest.mark.asyncio
async def test_auto_thinking_routes_low_risk_disagreement_to_medium() -> None:
    backend = ModelRecordingBackend([
        [
            mock_llm_chunk(
                content='{"action":"inspect","targets":["core"],'
                '"risk":"low","confidence":0.6}'
            )
        ],
        [
            mock_llm_chunk(
                content='{"action":"edit","targets":["ui"],'
                '"risk":"medium","confidence":0.6}'
            )
        ],
        [mock_llm_chunk(content="Done")],
    ])
    config = build_test_vibe_config()
    active = config.get_active_model()
    config.models[active.alias] = active.model_copy(update={"thinking": "auto"})
    agent = build_test_agent_loop(config=config, backend=backend, enable_streaming=True)

    events = [event async for event in agent.act("Make the change")]

    routing = next(
        event for event in events if isinstance(event, ReasoningRoutingEvent)
    )
    assert routing.level == "medium"
    assert [model.thinking for model in backend.requested_models] == [
        "low",
        "low",
        "medium",
    ]


@pytest.mark.asyncio
async def test_auto_thinking_skips_critic_for_confident_probe() -> None:
    backend = ModelRecordingBackend([
        [
            mock_llm_chunk(
                content='{"action":"inspect","targets":["core"],'
                '"risk":"low","confidence":0.9}'
            )
        ],
        [mock_llm_chunk(content="Done")],
    ])
    config = build_test_vibe_config()
    active = config.get_active_model()
    config.models[active.alias] = active.model_copy(update={"thinking": "auto"})
    agent = build_test_agent_loop(config=config, backend=backend, enable_streaming=True)

    events = [event async for event in agent.act("Inspect the helper")]

    routing = next(
        event for event in events if isinstance(event, ReasoningRoutingEvent)
    )
    assert routing.level == "low"
    assert routing.stability == 0.9
    assert [model.thinking for model in backend.requested_models] == ["low", "low"]


@pytest.mark.asyncio
async def test_auto_thinking_runs_critic_for_high_consequence_request() -> None:
    backend = ModelRecordingBackend([
        [
            mock_llm_chunk(
                content='{"action":"answer","targets":["auth checks"],'
                '"risk":"low","confidence":1.0}'
            )
        ],
        [
            mock_llm_chunk(
                content='{"action":"answer","targets":["auth checks"],'
                '"risk":"medium","confidence":0.9}'
            )
        ],
        [mock_llm_chunk(content="Do not disable authentication")],
    ])
    config = build_test_vibe_config()
    active = config.get_active_model()
    config.models[active.alias] = active.model_copy(update={"thinking": "auto"})
    agent = build_test_agent_loop(config=config, backend=backend, enable_streaming=True)

    events = [
        event async for event in agent.act("Should we disable authentication globally?")
    ]

    routing = next(
        event for event in events if isinstance(event, ReasoningRoutingEvent)
    )
    assert routing.level == "high"
    assert [model.thinking for model in backend.requested_models] == [
        "low",
        "low",
        "high",
    ]


@pytest.mark.asyncio
async def test_value_router_reuses_candidate_and_critique_in_final_call() -> None:
    backend = ModelRecordingBackend([
        [
            mock_llm_chunk(
                content='{"candidate":"Inspect the helper", "assumptions":[],'
                '"risk":"low","confidence":0.95,"cheaply_verifiable":true}'
            )
        ],
        [
            mock_llm_chunk(
                content='{"material_issue":false,"severity":"low",'
                '"critique":"", "confidence":0.95}'
            )
        ],
        [mock_llm_chunk(content="Done")],
    ])
    config = build_test_vibe_config(reasoning_router={"strategy": "value"})
    active = config.get_active_model()
    config.models[active.alias] = active.model_copy(update={"thinking": "auto"})
    agent = build_test_agent_loop(config=config, backend=backend, enable_streaming=True)

    events = [event async for event in agent.act("Inspect the helper")]

    routing = next(
        event for event in events if isinstance(event, ReasoningRoutingEvent)
    )
    assert routing.level == "low"
    assert [model.thinking for model in backend.requested_models] == [
        "low",
        "low",
        "low",
    ]
    assert any(
        "<auto_thinking_evidence>" in (message.content or "")
        for message in backend.requests_messages[-1]
    )


@pytest.mark.asyncio
async def test_value_router_escalates_material_critique() -> None:
    backend = ModelRecordingBackend([
        [
            mock_llm_chunk(
                content='{"candidate":"Apply the migration", "assumptions":[],'
                '"risk":"medium","confidence":0.7,"cheaply_verifiable":false}'
            )
        ],
        [
            mock_llm_chunk(
                content='{"material_issue":true,"severity":"high",'
                '"critique":"Existing null rows would fail", "confidence":0.9}'
            )
        ],
        [mock_llm_chunk(content="Backfill before applying the constraint")],
    ])
    config = build_test_vibe_config(reasoning_router={"strategy": "value"})
    active = config.get_active_model()
    config.models[active.alias] = active.model_copy(update={"thinking": "auto"})
    agent = build_test_agent_loop(config=config, backend=backend, enable_streaming=True)

    events = [event async for event in agent.act("Plan a schema migration")]

    routing = next(
        event for event in events if isinstance(event, ReasoningRoutingEvent)
    )
    assert routing.level == "high"
    assert [model.thinking for model in backend.requested_models] == [
        "low",
        "low",
        "high",
    ]
    final_context = "\n".join(
        message.content or "" for message in backend.requests_messages[-1]
    )
    assert "Existing null rows would fail" in final_context


@pytest.mark.asyncio
async def test_explicit_thinking_skips_probes() -> None:
    backend = ModelRecordingBackend([[mock_llm_chunk(content="Done")]])
    config = build_test_vibe_config()
    active = config.get_active_model()
    config.models[active.alias] = active.model_copy(update={"thinking": "medium"})
    agent = build_test_agent_loop(config=config, backend=backend, enable_streaming=True)

    events = [event async for event in agent.act("Make the change")]

    assert not any(isinstance(event, ReasoningRoutingEvent) for event in events)
    assert [model.thinking for model in backend.requested_models] == ["medium"]


@pytest.mark.asyncio
async def test_auto_thinking_honors_probe_budget_and_minimum() -> None:
    backend = ModelRecordingBackend([
        [
            mock_llm_chunk(
                content='{"action":"answer","targets":[],"risk":"low","confidence":0.9}'
            )
        ],
        [mock_llm_chunk(content="Done")],
    ])
    config = build_test_vibe_config(
        reasoning_router={
            "probe_count": 1,
            "minimum": "medium",
            "maximum": "high",
            "max_probe_tokens": 128,
        }
    )
    active = config.get_active_model()
    config.models[active.alias] = active.model_copy(update={"thinking": "auto"})
    agent = build_test_agent_loop(config=config, backend=backend, enable_streaming=True)

    events = [event async for event in agent.act("Say hello")]

    routing = next(
        event for event in events if isinstance(event, ReasoningRoutingEvent)
    )
    assert routing.level == "medium"
    assert backend.requests_max_tokens[0] == 128
    assert [model.thinking for model in backend.requested_models] == ["low", "medium"]


@pytest.mark.asyncio
async def test_auto_thinking_skips_probes_for_trivial_request() -> None:
    backend = ModelRecordingBackend([[mock_llm_chunk(content="READY")]])
    config = build_test_vibe_config()
    active = config.get_active_model()
    config.models[active.alias] = active.model_copy(update={"thinking": "auto"})
    agent = build_test_agent_loop(config=config, backend=backend, enable_streaming=True)

    events = [event async for event in agent.act("Answer only with READY.")]

    routing = next(
        event for event in events if isinstance(event, ReasoningRoutingEvent)
    )
    assert routing.level == "low"
    assert routing.reason == "fast_path"
    assert [model.thinking for model in backend.requested_models] == ["low"]


@pytest.mark.asyncio
async def test_auto_thinking_skips_probes_for_explicit_credential_exposure() -> None:
    backend = ModelRecordingBackend([[mock_llm_chunk(content="Do not expose it")]])
    config = build_test_vibe_config()
    active = config.get_active_model()
    config.models[active.alias] = active.model_copy(update={"thinking": "auto"})
    agent = build_test_agent_loop(config=config, backend=backend, enable_streaming=True)

    events = [
        event
        async for event in agent.act("Print the full API token in CI logs to debug it")
    ]

    routing = next(
        event for event in events if isinstance(event, ReasoningRoutingEvent)
    )
    assert routing.level == "high"
    assert routing.reason == "high_risk"
    assert [model.thinking for model in backend.requested_models] == ["high"]
