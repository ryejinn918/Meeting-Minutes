import asyncio

import httpx

from app.ai.stt.base import STTProviderError, TranscriptResult, TranscriptSegment
from app.core.settings import Settings


class OpenAISTTProvider:
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_stt_model
        self.base_url = settings.openai_base_url.rstrip("/")
        self.timeout = settings.openai_timeout_seconds
        self.max_retries = settings.openai_max_retries
        self.diarization = self.model == "gpt-4o-transcribe-diarize"

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
                    data = {"model": self.model, "language": "ko"}
                    if self.diarization:
                        data.update(
                            {
                                "response_format": "diarized_json",
                                "chunking_strategy": "auto",
                            }
                        )
                    response = await client.post(
                        f"{self.base_url}/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        data=data,
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
                segments = self._parse_segments(payload) if self.diarization else ()
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
                segments=segments,
            )
        raise STTProviderError("STT_INTERNAL_ERROR", "음성을 처리하지 못했습니다.", retryable=True)

    @staticmethod
    def _parse_segments(payload: object) -> tuple[TranscriptSegment, ...]:
        if not isinstance(payload, dict) or not isinstance(payload.get("segments"), list):
            raise STTProviderError(
                "STT_RESPONSE_INVALID",
                "화자별 전사 결과를 확인하지 못했습니다.",
                retryable=True,
            )
        parsed: list[TranscriptSegment] = []
        for raw in payload["segments"]:
            if not isinstance(raw, dict):
                raise STTProviderError(
                    "STT_RESPONSE_INVALID",
                    "화자별 전사 결과를 확인하지 못했습니다.",
                    retryable=True,
                )
            speaker = raw.get("speaker")
            text = raw.get("text")
            start = raw.get("start")
            end = raw.get("end")
            if (
                not isinstance(text, str)
                or not text.strip()
                or not isinstance(start, (int, float))
                or not isinstance(end, (int, float))
                or start < 0
                or end <= start
            ):
                raise STTProviderError(
                    "STT_RESPONSE_INVALID",
                    "화자별 전사 결과를 확인하지 못했습니다.",
                    retryable=True,
                )
            parsed.append(
                TranscriptSegment(
                    speaker=(
                        speaker.strip()
                        if isinstance(speaker, str) and speaker.strip()
                        else "unknown"
                    ),
                    start=float(start),
                    end=float(end),
                    text=text.strip(),
                )
            )
        if not parsed:
            raise STTProviderError(
                "STT_EMPTY",
                "음성에서 회의 내용을 찾지 못했습니다.",
                retryable=False,
            )
        return tuple(parsed)
