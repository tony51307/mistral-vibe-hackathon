from __future__ import annotations

import os
from typing import Any
from unittest.mock import Mock, patch

import pytest

from mistral_client import MistralClient, ModelBackendError


def _response(payload: dict[str, Any], error: Exception | None = None) -> Mock:
    response = Mock()
    response.json.return_value = payload
    if error is not None:
        response.raise_for_status.side_effect = error
    return response


def _openai_payload(text: str = '{"answer":"42"}') -> dict[str, Any]:
    return {
        "model": "gpt-5.6-luna",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": text}]},
        ],
        "usage": {"input_tokens": 12, "output_tokens": 7},
    }


def test_openai_selection_uses_responses_api() -> None:
    with (
        patch.dict(os.environ, {"OPENAI_API_KEY": "openai-test-key"}, clear=True),
        patch(
            "model_client.requests.post", return_value=_response(_openai_payload())
        ) as post,
    ):
        result = MistralClient("openai").complete("What is 6 * 7?", "high")

    assert result.provider == "openai"
    assert result.model == "gpt-5.6-luna"
    assert result.text == '{"answer":"42"}'
    assert result.input_tokens == 12
    assert result.output_tokens == 7
    url = post.call_args.args[0]
    request = post.call_args.kwargs
    assert url == "https://api.openai.com/v1/responses"
    assert request["json"]["model"] == "gpt-5.6-luna"
    assert request["json"]["reasoning"] == {"effort": "high"}
    assert request["json"]["store"] is False
    assert request["headers"]["Authorization"] == "Bearer openai-test-key"


def test_openai_selection_does_not_call_mistral() -> None:
    with (
        patch.dict(
            os.environ,
            {
                "MISTRAL_API_KEY": "mistral-test-key",
                "OPENAI_API_KEY": "openai-test-key",
            },
            clear=True,
        ),
        patch(
            "model_client.requests.post", return_value=_response(_openai_payload())
        ) as post,
    ):
        result = MistralClient("openai").complete("What is 6 * 7?", "medium")

    assert result.provider == "openai"
    assert [call.args[0] for call in post.call_args_list] == [
        "https://api.openai.com/v1/responses"
    ]


def test_mistral_selection_uses_mistral_api() -> None:
    payload = {
        "choices": [{"message": {"content": '{"answer":"42"}'}}],
        "usage": {"prompt_tokens": 9, "completion_tokens": 5},
    }
    with (
        patch.dict(
            os.environ,
            {
                "MISTRAL_API_KEY": "mistral-test-key",
                "OPENAI_API_KEY": "openai-test-key",
            },
            clear=True,
        ),
        patch("model_client.requests.post", return_value=_response(payload)) as post,
    ):
        result = MistralClient("mistral").complete("What is 6 * 7?", "low")

    assert result.provider == "mistral"
    assert post.call_count == 1
    assert post.call_args.args[0] == "https://api.mistral.ai/v1/chat/completions"


def test_selected_backend_requires_its_own_key() -> None:
    with patch.dict(os.environ, {"MISTRAL_API_KEY": "mistral-test-key"}, clear=True):
        client = MistralClient("openai")
        assert not client.enabled
        with pytest.raises(ModelBackendError, match="set OPENAI_API_KEY"):
            client.complete("prompt", "low")
