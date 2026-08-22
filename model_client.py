from __future__ import annotations

from dataclasses import dataclass
import json
import os
from time import perf_counter
from typing import Any, Literal

from dotenv import load_dotenv
import requests

load_dotenv()

ModelProvider = Literal["mistral", "openai"]


_MISTRAL_MAX_TOKENS = {"none": 32, "low": 96, "medium": 192, "high": 384, "xhigh": 512}

_OPENAI_MAX_OUTPUT_TOKENS = {
    "none": 64,
    "low": 192,
    "medium": 512,
    "high": 1024,
    "xhigh": 2048,
}


@dataclass(frozen=True)
class ModelResult:
    text: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    raw: dict[str, Any] | None = None


class MistralBackend:
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
        started = perf_counter()
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
                "max_tokens": _MISTRAL_MAX_TOKENS.get(tier, _MISTRAL_MAX_TOKENS["low"]),
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
            provider="mistral",
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            latency_ms=round((perf_counter() - started) * 1000),
            raw=payload,
        )


class OpenAIResponsesBackend:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip()
        self.base_url = os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str, tier: str) -> ModelResult:
        if not self.enabled:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        started = perf_counter()
        response = requests.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": prompt,
                "reasoning": {"effort": tier},
                "max_output_tokens": _OPENAI_MAX_OUTPUT_TOKENS.get(
                    tier, _OPENAI_MAX_OUTPUT_TOKENS["low"]
                ),
                "store": False,
            },
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage", {})
        return ModelResult(
            text=_openai_output_text(payload),
            model=str(payload.get("model") or self.model),
            provider="openai",
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            latency_ms=round((perf_counter() - started) * 1000),
            raw=payload,
        )


class ModelBackendError(RuntimeError):
    pass


class MistralClient:
    def __init__(self, provider: ModelProvider = "mistral") -> None:
        if provider not in {"mistral", "openai"}:
            raise ValueError(f"Unsupported model provider: {provider}")
        self.provider = provider
        self.mistral = MistralBackend()
        self.openai = OpenAIResponsesBackend()

    @property
    def enabled(self) -> bool:
        return self._backend.enabled

    @property
    def available(self) -> bool:
        return self.enabled

    def complete(self, prompt: str, tier: str) -> ModelResult:
        if not self.enabled:
            key = "MISTRAL_API_KEY" if self.provider == "mistral" else "OPENAI_API_KEY"
            raise ModelBackendError(
                f"The selected {self.provider} backend is not configured; set {key}"
            )
        return self._backend.complete(prompt, tier)

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        strong: bool = False,
        temperature: float = 0.2,
        retries: int = 2,
    ) -> dict[str, Any]:
        del temperature, retries
        tier = "high" if strong else "low"
        result = self.complete(f"{system}\n\n{user}", tier)
        return _parse_json(result.text)

    @property
    def _backend(self) -> MistralBackend | OpenAIResponsesBackend:
        if self.provider == "mistral":
            return self.mistral
        return self.openai


def _openai_output_text(payload: dict[str, Any]) -> str:
    if output_text := payload.get("output_text"):
        return str(output_text)

    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict) or content.get("type") != "output_text":
                continue
            if text := content.get("text"):
                parts.append(str(text))
    if parts:
        return "".join(parts)
    raise ValueError("OpenAI Responses payload did not contain output text")


def extract_answer(text: str) -> str:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and "answer" in payload:
            return str(payload["answer"]).strip()
    except json.JSONDecodeError:
        pass
    return text.strip().splitlines()[-1].strip()


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
