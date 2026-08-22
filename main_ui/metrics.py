"""Scoreboard and demo statistics."""

from __future__ import annotations

from typing import Any


def empty_stats(name: str, start_bankroll: int) -> dict[str, Any]:
    return {
        "name": name,
        "start_bankroll": start_bankroll,
        "bankroll": start_bankroll,
        "rounds_played": 0,
        "rounds_declined": 0,
        "correct": 0,
        "incorrect": 0,
        "credits_spent": 0,
        "prize_won": 0,
        "net_profit": 0,
        "accuracy": 0.0,
        "reward_per_credit": 0.0,
        "cheap_calls": 0,
        "perturbation_calls": 0,
        "deep_calls": 0,
        "deep_trigger_rounds": 0,
        "deep_changed_rounds": 0,
        "useful_revisions": [],
    }


def update_after_round(stats: dict[str, Any], result: dict[str, Any]) -> None:
    if result["decision"] == "DECLINE":
        stats["rounds_declined"] += 1
    else:
        stats["rounds_played"] += 1
        stats["credits_spent"] += result["spent"]
        if result["correct"]:
            stats["correct"] += 1
            stats["prize_won"] += result["payout"]
        elif result.get("submitted"):
            stats["incorrect"] += 1

    extras = result.get("metrics") or {}
    for key in ("cheap_calls", "perturbation_calls", "deep_calls"):
        stats[key] += extras.get(key, 0)
    if extras.get("deep_triggered"):
        stats["deep_trigger_rounds"] += 1
    if extras.get("changed_answer"):
        stats["deep_changed_rounds"] += 1
    if extras.get("useful_revision"):
        stats["useful_revisions"].append(extras["useful_revision"])

    played = stats["rounds_played"]
    stats["accuracy"] = (stats["correct"] / played) if played else 0.0
    stats["net_profit"] = stats["bankroll"] - stats["start_bankroll"]
    spent = stats["credits_spent"]
    stats["reward_per_credit"] = (stats["prize_won"] / spent) if spent else 0.0


def attach_bankroll(stats: dict[str, Any], bankroll: int) -> None:
    stats["bankroll"] = bankroll
    stats["net_profit"] = bankroll - stats["start_bankroll"]


def summary(all_stats: list[dict[str, Any]], dynamic: dict[str, Any] | None) -> dict[str, Any]:
    richest = max(all_stats, key=lambda s: s["bankroll"])
    most_accurate = max(all_stats, key=lambda s: (s["accuracy"], s["correct"]))
    most_efficient = max(all_stats, key=lambda s: s["reward_per_credit"])
    played_dyn = max((dynamic or {}).get("rounds_played", 0), 1)
    return {
        "winner": richest["name"],
        "winner_bankroll": richest["bankroll"],
        "most_accurate": most_accurate["name"],
        "most_accurate_rate": most_accurate["accuracy"],
        "most_efficient": most_efficient["name"],
        "efficiency": most_efficient["reward_per_credit"],
        "dynamic_trigger_rate": (
            (dynamic or {}).get("deep_trigger_rounds", 0) / played_dyn if dynamic else 0
        ),
        "best_revision": ((dynamic or {}).get("useful_revisions") or [None])[0],
    }
