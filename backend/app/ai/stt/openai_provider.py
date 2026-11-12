import asyncio
import logging
import time

import httpx

from app.ai.stt.base import STTProviderError, TranscriptResult, TranscriptSegment
from app.core.settings import Settings

logger = logging.getLogger("uvicorn.error")


class OpenAISTTProvider:
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_stt_model
        self.base_url = settings.openai_base_url.rstrip("/")
        self.base_timeout = settings.openai_timeout_seconds
        self.timeout_per_audio_second = settings.openai_timeout_per_audio_second
        self.max_timeout = settings.openai_timeout_max_seconds
        self.connect_timeout = settings.openai_connect_timeout_seconds
        self.write_timeout = settings.openai_write_timeout_seconds
        self.max_retries = settings.openai_max_retries
        self.diarization = self.model == "gpt-4o-transcribe-diarize"

    async def transcribe(
        self,
        content: bytes,
        *,
        filename: str,
        content_type: str,
        duration_seconds: float | None = None,
    ) -> TranscriptResult:
        if not self.api_key:
            raise STTProviderError(
                "OPENAI_NOT_CONFIGURED",
                "음성 전사 설정을 확인해 주세요.",
                retryable=False,
            )
        read_timeout = self._read_timeout(duration_seconds)
        timeout = httpx.Timeout(
            read_timeout,
            connect=self.connect_timeout,
            read=read_timeout,
            write=self.write_timeout,
            pool=self.connect_timeout,
        )
        for attempt in range(self.max_retries + 1):
            started = time.perf_counter()
            try:
                logger.info(
                    "stt_request_started model=%s attempt=%s audio_bytes=%s "
                    "audio_seconds=%s read_timeout_seconds=%s",
                    self.model,
                    attempt + 1,
                    len(content),
                    round(duration_seconds, 3) if duration_seconds is not None else "unknown",
                    round(read_timeout, 3),
                )
                async with httpx.AsyncClient(timeout=timeout) as client:
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
            except httpx.ConnectTimeout as exc:
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                logger.warning(
                    "stt_request_timeout kind=connect attempt=%s elapsed_seconds=%.3f",
                    attempt + 1,
                    time.perf_counter() - started,
                )
                raise STTProviderError(
                    "STT_TIMEOUT",
                    "음성 처리 시간이 초과되었습니다. 다시 시도해 주세요.",
                    retryable=True,
                ) from exc
            except httpx.TimeoutException as exc:
                logger.warning(
                    "stt_request_timeout kind=%s attempt=%s elapsed_seconds=%.3f",
                    type(exc).__name__,
                    attempt + 1,
                    time.perf_counter() - started,
                )
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
            logger.info(
                "stt_request_completed attempt=%s status=%s elapsed_seconds=%.3f "
                "request_id=%s",
                attempt + 1,
                response.status_code,
                time.perf_counter() - started,
                response.headers.get("x-request-id", "unknown"),
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

    def _read_timeout(self, duration_seconds: float | None) -> float:
        if duration_seconds is None:
            return self.base_timeout
        adaptive = duration_seconds * self.timeout_per_audio_second
        return min(max(self.base_timeout, adaptive), self.max_timeout)

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
