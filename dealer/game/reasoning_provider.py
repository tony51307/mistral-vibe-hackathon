from __future__ import annotations

from typing import Any, Mapping, Protocol

from .models import ReasoningTier


REASONING_MAPPING_VERSION = "abstract-v1"


def reasoning_config(tier: ReasoningTier | str) -> dict[str, str]:
    """Single provider-adapter boundary for abstract game tiers.

    The concrete Mistral adapter can replace these abstract values without
    changing the dealer or its game-dollar prices.
    """
    normalized = ReasoningTier(tier)
    return {"tier": normalized.value, "mapping_version": REASONING_MAPPING_VERSION}


class Router(Protocol):
    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class Solver(Protocol):
    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...
