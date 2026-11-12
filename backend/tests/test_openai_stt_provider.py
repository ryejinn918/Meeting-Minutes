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
    init_kwargs: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.init_kwargs.append(kwargs)

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
    StubClient.init_kwargs = []
    monkeypatch.setattr("app.ai.stt.openai_provider.httpx.AsyncClient", StubClient)
    yield


def settings(
    *, retries: int = 0, model: str = "gpt-transcribe"
) -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key="test-secret",
        openai_stt_model=model,
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
async def test_diarization_model_requests_and_parses_diarized_json() -> None:
    StubClient.queue = [
        httpx.Response(
            200,
            json={
                "text": "첫 번째 발언 두 번째 발언",
                "segments": [
                    {
                        "speaker": "A",
                        "start": 0.0,
                        "end": 4.2,
                        "text": "첫 번째 발언",
                    },
                    {
                        "speaker": "B",
                        "start": 4.2,
                        "end": 8.0,
                        "text": "두 번째 발언",
                    },
                ],
                "usage": {"type": "duration", "seconds": 8},
            },
        )
    ]

    result = await OpenAISTTProvider(
        settings(model="gpt-4o-transcribe-diarize")
    ).transcribe(b"ID3audio", filename="meeting.mp3", content_type="audio/mpeg")

    request = StubClient.requests[0]
    assert request["data"] == {
        "model": "gpt-4o-transcribe-diarize",
        "language": "ko",
        "response_format": "diarized_json",
        "chunking_strategy": "auto",
    }
    assert [(item.speaker, item.start, item.end) for item in result.segments] == [
        ("A", 0.0, 4.2),
        ("B", 4.2, 8.0),
    ]


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


@pytest.mark.asyncio
async def test_read_timeout_is_not_immediately_retried() -> None:
    StubClient.queue = [httpx.ReadTimeout("timeout")]

    with pytest.raises(STTProviderError) as error:
        await OpenAISTTProvider(settings(retries=1)).transcribe(
            b"ID3audio",
            filename="meeting.mp3",
            content_type="audio/mpeg",
            duration_seconds=600,
        )

    assert error.value.code == "STT_TIMEOUT"
    assert len(StubClient.requests) == 1


@pytest.mark.asyncio
async def test_long_audio_uses_duration_based_read_timeout() -> None:
    StubClient.queue = [httpx.Response(200, json={"text": "회의 전사 결과"})]

    await OpenAISTTProvider(settings()).transcribe(
        b"ID3audio",
        filename="meeting.mp3",
        content_type="audio/mpeg",
        duration_seconds=600,
    )

    timeout = StubClient.init_kwargs[0]["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.read == 360
