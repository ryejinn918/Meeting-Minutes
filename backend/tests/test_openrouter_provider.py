import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx
import pytest

from app.ai.analysis.base import AIProviderError
from app.ai.analysis.openrouter_provider import OpenRouterAnalysisProvider
from app.core.settings import Settings


def valid_payload() -> dict[str, Any]:
    return {
        "summary": "핵심 요약",
        "key_discussions": [],
        "decisions": [],
        "action_items": [
            {
                "description": "API 연결",
                "assignee_name": None,
                "due_date": None,
                "status": "todo",
                "evidence": None,
            }
        ],
        "follow_ups": [],
    }


class StubClient(AbstractAsyncContextManager["StubClient"]):
    queue: list[httpx.Response | Exception] = []
    requests: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "StubClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.requests.append({"url": url, **kwargs})
        value = self.queue.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture(autouse=True)
def reset_stub(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    StubClient.queue = []
    StubClient.requests = []
    monkeypatch.setattr("app.ai.analysis.openrouter_provider.httpx.AsyncClient", StubClient)
    yield


def settings(*, retries: int = 0) -> Settings:
    return Settings(
        _env_file=None,
        openrouter_api_key="test-secret",
        openrouter_analysis_model="deepseek/deepseek-v3.2",
        openrouter_max_retries=retries,
    )


def response(status: int, content: str | dict[str, Any]) -> httpx.Response:
    body = {
        "id": "request-id",
        "model": "deepseek/deepseek-v3.2",
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        "choices": [{"message": {"content": content}}],
    }
    return httpx.Response(status, json=body)


@pytest.mark.asyncio
async def test_parses_structured_response_with_null_fields_and_empty_arrays() -> None:
    StubClient.queue = [response(200, json.dumps(valid_payload()))]

    result = await OpenRouterAnalysisProvider(settings()).analyze(
        "회의 전문", meeting_date=__import__("datetime").date(2026, 11, 11)
    )

    assert result.analysis.action_items[0].assignee_name is None
    assert result.analysis.action_items[0].due_date is None
    assert result.analysis.decisions == []
    assert result.usage["prompt_tokens"] == 20
    sent = StubClient.requests[0]["json"]
    assert sent["model"] == "deepseek/deepseek-v3.2"
    assert sent["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_invalid_json_is_rejected() -> None:
    StubClient.queue = [response(200, "not-json")]

    with pytest.raises(AIProviderError, match="형식") as error:
        await OpenRouterAnalysisProvider(settings()).analyze(
            "회의 전문", meeting_date=__import__("datetime").date(2026, 11, 11)
        )

    assert error.value.code == "AI_INVALID_RESPONSE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_code", "retryable"),
    [
        (401, "AI_AUTHENTICATION_ERROR", False),
        (429, "AI_RATE_LIMITED", True),
    ],
)
async def test_provider_http_errors(
    status_code: int, expected_code: str, retryable: bool
) -> None:
    StubClient.queue = [httpx.Response(status_code)]

    with pytest.raises(AIProviderError) as error:
        await OpenRouterAnalysisProvider(settings()).analyze(
            "회의 전문", meeting_date=__import__("datetime").date(2026, 11, 11)
        )

    assert error.value.code == expected_code
    assert error.value.retryable is retryable


@pytest.mark.asyncio
async def test_timeout_is_retryable() -> None:
    StubClient.queue = [httpx.ReadTimeout("timeout")]

    with pytest.raises(AIProviderError) as error:
        await OpenRouterAnalysisProvider(settings()).analyze(
            "회의 전문", meeting_date=__import__("datetime").date(2026, 11, 11)
        )

    assert error.value.code == "AI_TIMEOUT"
    assert error.value.retryable is True


@pytest.mark.asyncio
async def test_invalid_response_gets_one_schema_repair_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.ai.analysis.openrouter_provider.asyncio.sleep", no_sleep)
    StubClient.queue = [
        response(200, "{}"),
        response(200, json.dumps(valid_payload())),
    ]

    result = await OpenRouterAnalysisProvider(settings(retries=1)).analyze(
        "회의 전문", meeting_date=__import__("datetime").date(2026, 11, 11)
    )

    assert result.analysis.summary == "핵심 요약"
    assert len(StubClient.requests) == 2
    repair_message = StubClient.requests[1]["json"]["messages"][-1]["content"]
    assert "JSON 스키마" in repair_message
