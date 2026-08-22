"""Mistral API wrapper with JSON parsing, retries, and offline fallback."""

from __future__ import annotations

import json
import os
import time
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


CHEAP_COST = 2
PERTURB_COST = 1
DEEP_COST = 8
DYNAMIC_COST = 5


class MistralClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("MISTRAL_API_KEY", "").strip()
        self.cheap_model = os.getenv("MISTRAL_CHEAP_MODEL", "mistral-small-latest")
        self.strong_model = os.getenv("MISTRAL_STRONG_MODEL", "mistral-small-latest")
        self._client = None
        if self.api_key:
            try:
                try:
                    from mistralai import Mistral
                except ImportError:
                    from mistralai.client import Mistral

                self._client = Mistral(api_key=self.api_key)
            except Exception:
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        strong: bool = False,
        temperature: float = 0.2,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        retries: int = 2,
    ) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("Mistral client unavailable; use seeded stubs.")

        model = self.strong_model if strong else self.cheap_model
        last_err: Exception | None = None
        current_reasoning_effort = reasoning_effort
        for attempt in range(retries + 1):
            try:
                resp = self._client.chat.complete(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                    reasoning_effort=current_reasoning_effort,
                )
                text = resp.choices[0].message.content or "{}"
                data = _parse_json(text)
                data["_model"] = model
                usage = getattr(resp, "usage", None)
                if usage is not None:
                    data["_usage"] = {
                        "prompt_tokens": getattr(usage, "prompt_tokens", None),
                        "completion_tokens": getattr(usage, "completion_tokens", None),
                        "total_tokens": getattr(usage, "total_tokens", None),
                    }
                return data
            except Exception as exc:
                last_err = exc
                if current_reasoning_effort is not None and "reasoning_effort" in str(exc):
                    current_reasoning_effort = None
                    continue
                time.sleep(0.4 * (attempt + 1))
        raise RuntimeError(f"Mistral call failed: {last_err}")


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"raw": data}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        return {"answer": text, "confidence": 0.4, "reasoning": text}
