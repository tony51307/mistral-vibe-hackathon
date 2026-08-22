"""Pay-to-Think dealer core."""

from .judge import judge_answer
from .loaders import load_agendas, load_problem_bank, load_table_modes
from .models import GameConfig, Phase, ReasoningTier, TableCatalog, TableMode


def __getattr__(name: str):
    if name in {"DealerGame", "SeasonComplete"}:
        from .dealer_distributor import DealerGame, SeasonComplete

        return {"DealerGame": DealerGame, "SeasonComplete": SeasonComplete}[name]
    raise AttributeError(name)

__all__ = [
    "DealerGame",
    "GameConfig",
    "Phase",
    "ReasoningTier",
    "SeasonComplete",
    "TableCatalog",
    "TableMode",
    "judge_answer",
    "load_agendas",
    "load_problem_bank",
    "load_table_modes",
]
