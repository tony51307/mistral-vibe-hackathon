from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from model_client import (
    MistralClient,
    ModelBackendError,
    ModelProvider,
    ModelResult,
    extract_answer,
)

CHEAP_COST = 2
PERTURB_COST = 1
DEEP_COST = 8
DYNAMIC_COST = 5


__all__ = [
    "CHEAP_COST",
    "DEEP_COST",
    "DYNAMIC_COST",
    "PERTURB_COST",
    "MistralClient",
    "ModelBackendError",
    "ModelProvider",
    "ModelResult",
    "extract_answer",
]
