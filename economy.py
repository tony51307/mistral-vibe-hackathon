from __future__ import annotations

from dataclasses import dataclass


REASONING_PRICES: dict[str, int] = {
    "none": 1,
    "low": 2,
    "medium": 3,
    "high": 5,
    "xhigh": 9,
}


TIER_ORDER = ["none", "low", "medium", "high", "xhigh"]


@dataclass(frozen=True)
class EconomyConfig:
    players: int = 4
    starting_bankroll: int = 80
    entry_fee: int = 10
    dealer_contribution: int = 12
    season_rounds: int = 25
    message_max_chars: int = 100
    max_rollover_chain_for_demo: int = 3


def affordable_tiers(bankroll_after_entry: float) -> list[str]:
    return [
        tier
        for tier in TIER_ORDER
        if REASONING_PRICES[tier] <= bankroll_after_entry
    ]


def highest_affordable_tier(bankroll_after_entry: float) -> str:
    tiers = affordable_tiers(bankroll_after_entry)
    return tiers[-1] if tiers else "none"


def clamp_tier_to_bankroll(tier: str, bankroll_after_entry: float) -> str:
    if tier not in REASONING_PRICES:
        return highest_affordable_tier(bankroll_after_entry)
    if REASONING_PRICES[tier] <= bankroll_after_entry:
        return tier
    return highest_affordable_tier(bankroll_after_entry)


def tier_index(tier: str) -> int:
    return TIER_ORDER.index(tier)

