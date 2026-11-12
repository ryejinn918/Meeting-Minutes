import asyncio

import httpx

from app.ai.stt.base import STTProviderError, TranscriptResult
from app.core.settings import Settings


class OpenAISTTProvider:
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_stt_model
        self.base_url = settings.openai_base_url.rstrip("/")
        self.timeout = settings.openai_timeout_seconds
        self.max_retries = settings.openai_max_retries

    async def transcribe(
        self, content: bytes, *, filename: str, content_type: str
    ) -> TranscriptResult:
        if not self.api_key:
            raise STTProviderError(
                "OPENAI_NOT_CONFIGURED",
                "음성 전사 설정을 확인해 주세요.",
                retryable=False,
            )
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        data={"model": self.model, "language": "ko"},
                        files={"file": (filename, content, content_type)},
                    )
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise STTProviderError(
                    "STT_TIMEOUT",
                    "음성 처리 시간이 초과되었습니다. 다시 시도해 주세요.",
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise STTProviderError(
                    "STT_UNAVAILABLE",
                    "음성 처리 서비스에 연결할 수 없습니다.",
                    retryable=True,
                ) from exc

            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code in {401, 403}:
                raise STTProviderError(
                    "STT_AUTHENTICATION_ERROR",
                    "음성 전사 설정을 확인해 주세요.",
                    retryable=False,
                )
            if response.status_code == 429:
                raise STTProviderError(
                    "STT_RATE_LIMITED",
                    "요청이 많아 음성을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                    retryable=True,
                )
            if response.status_code >= 400:
                raise STTProviderError(
                    "STT_REQUEST_REJECTED",
                    "이 음성파일을 처리하지 못했습니다. 파일 형식을 확인해 주세요.",
                    retryable=False,
                )
            try:
                payload = response.json()
                text = payload.get("text") if isinstance(payload, dict) else None
            except ValueError as exc:
                raise STTProviderError(
                    "STT_RESPONSE_INVALID",
                    "음성 전사 결과를 확인하지 못했습니다.",
                    retryable=True,
                ) from exc
            if not isinstance(text, str) or not text.strip():
                raise STTProviderError(
                    "STT_EMPTY",
                    "음성에서 회의 내용을 찾지 못했습니다.",
                    retryable=False,
                )
            return TranscriptResult(
                text=text.strip(),
                provider="openai",
                model=self.model,
                language="ko",
                request_id=response.headers.get("x-request-id"),
                usage=payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
            )
        raise STTProviderError("STT_INTERNAL_ERROR", "음성을 처리하지 못했습니다.", retryable=True)
