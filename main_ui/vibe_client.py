"""Vibe CLI programmatic solver wrapper for the demo UI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "main_ui" / ".env")


class VibeCliClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("MISTRAL_API_KEY", "").strip()
        self.cheap_model = os.getenv("MISTRAL_CHEAP_MODEL", "mistral-small-latest")
        self.strong_model = os.getenv("MISTRAL_STRONG_MODEL", "mistral-small-latest")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def solve_json(
        self,
        *,
        prompt: str,
        tier: str,
        policy: str,
        max_tokens: int = 256,
    ) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("MISTRAL_API_KEY is missing; Vibe CLI solver unavailable.")

        thinking = _thinking_for(policy, tier)
        model_name = self.strong_model if thinking in {"medium", "high", "max", "auto"} else self.cheap_model
        env = {
            **os.environ,
            "MISTRAL_API_KEY": self.api_key,
            "VIBE_ACTIVE_MODEL": "pay-to-think-demo",
            "VIBE_MODELS": json.dumps(
                [
                    {
                        "name": model_name,
                        "provider": "mistral",
                        "alias": "pay-to-think-demo",
                        "display_name": "Pay-to-Think Demo",
                        "temperature": 0.1,
                        "thinking": thinking,
                    }
                ]
            ),
        }
        result = subprocess.run(
            [
                "uv",
                "run",
                "vibe",
                "-p",
                _vibe_prompt(prompt, tier, thinking),
                "--max-turns",
                "1",
                "--max-tokens",
                str(max_tokens),
                "--enabled-tools",
                "re:^$",
                "--trust",
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
        if result.returncode != 0:
            error = (result.stderr or result.stdout or "unknown Vibe CLI error").strip()
            raise RuntimeError(error[:500])
        data = _parse_json(result.stdout)
        data["_model"] = f"vibe-cli:{model_name}"
        data["_vibe_thinking"] = thinking
        return data


def _thinking_for(policy: str, tier: str) -> str:
    if policy == "always_none":
        return "off"
    if policy == "perturbation_router":
        return "auto"
    match tier:
        case "none":
            return "off"
        case "low":
            return "low"
        case "medium":
            return "medium"
        case "high":
            return "high"
        case "xhigh":
            return "max"
        case _:
            return "off"


def _vibe_prompt(prompt: str, tier: str, thinking: str) -> str:
    return (
        "Solve the math problem below. Return JSON only, with exactly these keys: "
        '{"answer": string, "confidence": number, "reasoning": string}. '
        "The answer must be a concise scalar when possible.\n\n"
        f"Allowed reasoning tier bid: {tier}\n"
        f"Vibe thinking mode: {thinking}\n\n"
        f"{prompt}"
    )


def _parse_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else {"raw": data}
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(stripped[start : end + 1])
            return data if isinstance(data, dict) else {"raw": data}
    return {"answer": stripped, "confidence": 0.4, "reasoning": stripped}
