from __future__ import annotations

import pytest

from tests.conftest import build_test_vibe_app
from vibe.app_server.models import (
    ReasoningRoutingNoticeDetail,
    ReasoningRoutingProgressNoticeDetail,
)
from vibe.cli.textual_ui.auto_thinking import AutoThinkSessionStats
from vibe.cli.textual_ui.widgets.messages import AutoThinkMessage, UserCommandMessage


def _detail(
    level: str = "high", stability: float = 0.6, reason: str = "disagreement"
) -> ReasoningRoutingNoticeDetail:
    return ReasoningRoutingNoticeDetail(level=level, stability=stability, reason=reason)


def test_auto_think_message_shows_route_and_safe_explanation() -> None:
    content = AutoThinkMessage(_detail()).render().plain

    assert "AutoThink → HIGH" in content
    assert "60%" in content
    assert "request → low-cost probes → uncertainty → HIGH" in content
    assert "probes disagreed" in content


def test_auto_think_message_updates_dynamic_routing_stages() -> None:
    message = AutoThinkMessage(
        progress=ReasoningRoutingProgressNoticeDetail(
            stage="analyzing", message="Scanning task complexity…"
        )
    )

    assert "ANALYZING" in message.render().plain
    message.update_progress(
        ReasoningRoutingProgressNoticeDetail(
            stage="verifying", message="Checking route stability…"
        )
    )
    assert "VERifying".upper() in message.render().plain
    assert "━━━━━━━━──" in message.render().plain
    message.complete(_detail())
    assert "AutoThink → HIGH" in message.render().plain


def test_auto_think_session_explains_latest_route() -> None:
    stats = AutoThinkSessionStats()
    stats.record(_detail(level="medium", stability=0.7))

    explanation = stats.explain_markdown()

    assert "chose MEDIUM" in explanation
    assert "70%" in explanation
    assert "not private chain-of-thought" in explanation


def test_auto_think_session_reports_counterfactual_savings() -> None:
    stats = AutoThinkSessionStats()
    stats.record(_detail(level="low"))
    stats.record(_detail(level="high"))
    stats.record(_detail(level="medium"))

    report = stats.stats_markdown()

    assert "Routed turns:** 3" in report
    assert "LOW 1 · MEDIUM 1 · HIGH 1" in report
    assert "High-effort calls avoided:** 2/3 (67%)" in report
    assert "exclude routing-probe overhead" in report


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subcommand", "expected"),
    [("explain", "AutoThink chose HIGH"), ("stats", "Routed turns:** 1")],
)
async def test_thinking_dashboard_commands(subcommand: str, expected: str) -> None:
    app = build_test_vibe_app()
    async with app.run_test() as pilot:
        app._auto_thinking_stats.record(_detail())

        await app._show_thinking(cmd_args=subcommand)
        await pilot.pause()

        messages = list(app.query(UserCommandMessage))
        assert expected in messages[-1]._content
