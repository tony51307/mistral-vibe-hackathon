from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class ModelResult:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    raw: dict[str, Any] | None = None


class MistralClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("MISTRAL_API_KEY", "")
        self.cheap_model = os.getenv("MISTRAL_CHEAP_MODEL", "mistral-small-latest")
        self.strong_model = os.getenv("MISTRAL_STRONG_MODEL", "mistral-large-latest")
        self.base_url = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str, tier: str) -> ModelResult:
        if not self.enabled:
            raise RuntimeError("MISTRAL_API_KEY is not configured")

        model = self.cheap_model if tier in {"none", "low"} else self.strong_model
        max_tokens = {
            "none": 32,
            "low": 96,
            "medium": 192,
            "high": 384,
            "xhigh": 512,
        }.get(tier, 96)

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": max_tokens,
            },
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        return ModelResult(
            text=text,
            model=model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            raw=payload,
        )


def extract_answer(text: str) -> str:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and "answer" in payload:
            return str(payload["answer"]).strip()
    except json.JSONDecodeError:
        pass
    return text.strip().splitlines()[-1].strip()

