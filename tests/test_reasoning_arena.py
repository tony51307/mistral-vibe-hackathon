from __future__ import annotations

from scripts.reasoning_arena import (
    ArenaReport,
    ArenaResult,
    ArenaTask,
    _result_from_history,
    render_markdown,
)


def test_result_extracts_auto_thinking_route() -> None:
    history = [
        {
            "type": "notice",
            "detail": {
                "kind": "reasoning_routed",
                "level": "high",
                "stability": 0.5,
                "reason": "disagreement",
            },
        },
        {
            "type": "message",
            "role": "assistant",
            "sessionId": "missing-session",
            "content": [{"type": "text", "text": "Inspect first."}],
        },
    ]

    task = ArenaTask(
        id="architecture",
        title="Architecture",
        prompt="Inspect first",
        expected_auto_level="high",
    )
    result = _result_from_history(task, "auto_adaptive", history, 1.25)

    assert result.response == "Inspect first."
    assert result.routed_level == "high"
    assert result.routing_reason == "disagreement"
    assert result.stability == 0.5


def test_markdown_reports_auto_routing_agreement() -> None:
    task = ArenaTask(
        id="simple", title="Simple", prompt="Say READY", expected_auto_level="low"
    )
    report = ArenaReport(
        created_at="2026-08-22T00:00:00+00:00",
        model="test-model",
        tasks=[task],
        results=[
            ArenaResult(
                task_id="simple",
                policy="auto_adaptive",
                response="READY",
                routed_level="low",
                elapsed_seconds=1,
                total_tokens=100,
                cost=0.001,
            )
        ],
    )

    markdown = render_markdown(report)

    assert "auto_adaptive routing agreement: **1/1" in markdown
    assert (
        "| Simple | 1 | auto_adaptive | low | — | 100 | $0.00100 | 1.00 |" in markdown
    )
    assert "| auto_adaptive | 1 | 0.0% | 100 | $0.00100 | 1.00 |" in markdown
