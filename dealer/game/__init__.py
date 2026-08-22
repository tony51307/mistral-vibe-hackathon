"""Pay-to-Think dealer core."""

from .agent_config import (
    AgentCatalog,
    AgentConfigError,
    AgentProfile,
    ResolvedLLMRuntime,
    RuntimeKind,
    load_agent_catalog,
    prepare_agent_context,
    resolve_llm_runtime,
)
from .judge import judge_answer
from .loaders import (
    load_agenda_catalogs,
    load_agendas,
    load_problem_bank,
    load_problem_banks,
    load_table_modes,
)
from .models import GameConfig, Phase, ReasoningTier, TableCatalog, TableMode


def __getattr__(name: str):
    if name in {"DealerGame", "SeasonComplete"}:
        from .dealer_distributor import DealerGame, SeasonComplete

        return {"DealerGame": DealerGame, "SeasonComplete": SeasonComplete}[name]
    raise AttributeError(name)


__all__ = [
    "DealerGame",
    "AgentCatalog",
    "AgentConfigError",
    "AgentProfile",
    "GameConfig",
    "Phase",
    "ReasoningTier",
    "ResolvedLLMRuntime",
    "RuntimeKind",
    "SeasonComplete",
    "TableCatalog",
    "TableMode",
    "judge_answer",
    "load_agenda_catalogs",
    "load_agendas",
    "load_agent_catalog",
    "load_problem_bank",
    "load_problem_banks",
    "load_table_modes",
    "prepare_agent_context",
    "resolve_llm_runtime",
]
