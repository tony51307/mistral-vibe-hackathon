from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from vibe.app_server.models import ReasoningRoutingNoticeDetail

_REASON_EXPLANATIONS = {
    "fast_path": "The request matched a simple, low-risk fast path.",
    "stable": "The low-cost probes agreed on a straightforward approach.",
    "disagreement": (
        "The probes disagreed or reported uncertainty, so Vibe increased reasoning."
    ),
    "high_risk": (
        "The task has high-impact or hard-to-detect failure modes, so Vibe escalated."
    ),
    "probe_failed": (
        "The routing probe was unavailable, so Vibe used its safe fallback level."
    ),
}


def routing_explanation(reason: str) -> str:
    return _REASON_EXPLANATIONS.get(
        reason, "Vibe selected the level from the available routing evidence."
    )


def routing_path(reason: str, level: str) -> str:
    middle = {
        "fast_path": "fast path",
        "stable": "low-cost probes → agreement",
        "disagreement": "low-cost probes → uncertainty",
        "high_risk": "risk guard",
        "probe_failed": "probe unavailable → safe fallback",
    }.get(reason, "routing evidence")
    return f"request → {middle} → {level.upper()}"


@dataclass(slots=True)
class AutoThinkSessionStats:
    counts: Counter[str] = field(default_factory=Counter)
    latest: ReasoningRoutingNoticeDetail | None = None

    def record(self, detail: ReasoningRoutingNoticeDetail) -> None:
        self.counts[detail.level] += 1
        self.latest = detail

    def explain_markdown(self) -> str:
        if self.latest is None:
            return (
                "### AutoThink\n\nNo automatic routing decision has been made in "
                "this session yet. Select `auto` with `/thinking`, then run a task."
            )
        return (
            f"### AutoThink chose {self.latest.level.upper()}\n\n"
            f"{routing_explanation(self.latest.reason)}\n\n"
            f"**Routing stability:** {self.latest.stability:.0%}\n\n"
            "This is a routing summary, not private chain-of-thought."
        )

    def stats_markdown(self) -> str:
        total = self.counts.total()
        if total == 0:
            return (
                "### AutoThink session\n\nNo routed turns yet. Select `auto` with "
                "`/thinking` to begin measuring."
            )
        below_high = sum(
            count
            for level, count in self.counts.items()
            if level in {"off", "low", "medium"}
        )
        distribution = " · ".join(
            f"{level.upper()} {self.counts[level]}"
            for level in ("off", "low", "medium", "high", "max")
            if self.counts[level]
        )
        return (
            "### AutoThink session\n\n"
            f"**Routed turns:** {total}  \n"
            f"**Thinking mix:** {distribution}  \n"
            f"**High-effort calls avoided:** {below_high}/{total} ({below_high / total:.0%})\n\n"
            "_Avoided calls are a counterfactual versus always-high mode and exclude "
            "routing-probe overhead._"
        )
