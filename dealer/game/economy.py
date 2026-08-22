from __future__ import annotations

from .models import GameConfig, ReasoningTier, TIER_ORDER


def affordable_tiers(bankroll_cents: int, config: GameConfig) -> tuple[ReasoningTier, ...]:
    if bankroll_cents < 0:
        raise ValueError("bankroll cannot be negative")
    return tuple(
        tier for tier in TIER_ORDER if config.reasoning_prices_cents[tier] <= bankroll_cents
    )


def highest_affordable_tier(bankroll_cents: int, config: GameConfig) -> ReasoningTier | None:
    tiers = affordable_tiers(bankroll_cents, config)
    return tiers[-1] if tiers else None


def split_pot(pot_cents: int, winner_count: int) -> tuple[int, int]:
    """Return (share_per_winner, remainder_to_rollover), exactly in cents."""
    if pot_cents < 0:
        raise ValueError("pot cannot be negative")
    if winner_count <= 0:
        return 0, pot_cents
    return divmod(pot_cents, winner_count)
