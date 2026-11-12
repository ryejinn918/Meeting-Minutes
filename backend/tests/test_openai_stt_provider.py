from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx
import pytest

from app.ai.stt.base import STTProviderError
from app.ai.stt.openai_provider import OpenAISTTProvider
from app.core.settings import Settings


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
    monkeypatch.setattr("app.ai.stt.openai_provider.httpx.AsyncClient", StubClient)
    yield


def settings(*, retries: int = 0) -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key="test-secret",
        openai_stt_model="gpt-transcribe",
        openai_max_retries=retries,
    )


@pytest.mark.asyncio
async def test_openai_stt_parses_text_without_guessing_speakers() -> None:
    StubClient.queue = [httpx.Response(200, json={"text": "회의 전사 결과"})]

    result = await OpenAISTTProvider(settings()).transcribe(
        b"ID3audio", filename="meeting.mp3", content_type="audio/mpeg"
    )

    assert result.text == "회의 전사 결과"
    assert result.model == "gpt-transcribe"
    request = StubClient.requests[0]
    assert request["data"] == {"model": "gpt-transcribe", "language": "ko"}
    assert "speaker" not in request["data"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "STT_AUTHENTICATION_ERROR", False),
        (429, "STT_RATE_LIMITED", True),
    ],
)
async def test_openai_stt_http_errors(status: int, code: str, retryable: bool) -> None:
    StubClient.queue = [httpx.Response(status)]

    with pytest.raises(STTProviderError) as error:
        await OpenAISTTProvider(settings()).transcribe(
            b"ID3audio", filename="meeting.mp3", content_type="audio/mpeg"
        )

    assert error.value.code == code
    assert error.value.retryable is retryable


@pytest.mark.asyncio
async def test_openai_stt_timeout_is_retryable() -> None:
    StubClient.queue = [httpx.ReadTimeout("timeout")]

    with pytest.raises(STTProviderError) as error:
        await OpenAISTTProvider(settings()).transcribe(
            b"ID3audio", filename="meeting.mp3", content_type="audio/mpeg"
        )

    assert error.value.code == "STT_TIMEOUT"
    assert error.value.retryable is True
