import asyncio
import json
from datetime import date
from typing import Any

import httpx
from pydantic import ValidationError

from app.ai.analysis.base import AIProviderError, AnalysisResult, CorrectionResult
from app.ai.prompts import (
    CORRECTION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_analysis_prompt,
    build_correction_prompt,
)
from app.core.settings import Settings
from app.schemas.analysis import MeetingAnalysis
from app.schemas.quality import TranscriptCorrectionResult


class OpenRouterAnalysisProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def analyze(
        self,
        transcript: str,
        *,
        meeting_date: date,
        context: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        if not self.settings.openrouter_api_key:
            raise AIProviderError(
                "OPENROUTER_NOT_CONFIGURED",
                "OpenRouter API 키가 설정되지 않았습니다.",
                retryable=False,
            )
        if not self.settings.openrouter_analysis_model:
            raise AIProviderError(
                "OPENROUTER_MODEL_NOT_CONFIGURED",
                "OpenRouter 분석 모델이 설정되지 않았습니다.",
                retryable=False,
            )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_analysis_prompt(transcript, meeting_date, context=context),
            },
        ]
        last_error: AIProviderError | None = None
        total_attempts = self.settings.openrouter_max_retries + 1
        for attempt in range(total_attempts):
            try:
                return await self._request(messages)
            except AIProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt + 1 >= total_attempts:
                    raise
                if exc.code == "AI_INVALID_RESPONSE":
                    messages = [
                        *messages,
                        {
                            "role": "system",
                            "content": (
                                "이전 응답 형식이 스키마와 일치하지 않았습니다. "
                                "설명이나 마크다운 없이 지정된 JSON 스키마만 정확히 반환하세요."
                            ),
                        },
                    ]
                await asyncio.sleep(0.25 * (2**attempt))
        assert last_error is not None
        raise last_error

    async def correct_transcript(
        self,
        transcript: str,
        *,
        topic: str,
        glossary: list[dict[str, Any]],
    ) -> CorrectionResult:
        if not self.settings.openrouter_api_key or not self.settings.openrouter_analysis_model:
            raise AIProviderError(
                "OPENROUTER_NOT_CONFIGURED",
                "회의 전문 교정 설정을 확인해 주세요.",
                retryable=False,
            )
        messages = [
            {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
            {"role": "user", "content": build_correction_prompt(transcript, topic, glossary)},
        ]
        total_attempts = self.settings.openrouter_max_retries + 1
        for attempt in range(total_attempts):
            try:
                body, response = await self._request_schema(
                    messages,
                    "transcript_correction",
                    TranscriptCorrectionResult.model_json_schema(),
                )
                content = body["choices"][0]["message"]["content"]
                raw = json.loads(content) if isinstance(content, str) else content
                correction = TranscriptCorrectionResult.model_validate(raw)
                return CorrectionResult(
                    correction=correction,
                    provider="openrouter",
                    model=str(body.get("model") or self.settings.openrouter_analysis_model),
                    usage=body.get("usage") if isinstance(body.get("usage"), dict) else {},
                    request_id=response.headers.get("x-request-id") or body.get("id"),
                )
            except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
                error = AIProviderError(
                    "AI_INVALID_RESPONSE",
                    "전문 교정 결과 형식이 올바르지 않습니다.",
                    retryable=True,
                )
                if attempt + 1 >= total_attempts:
                    raise error from exc
                messages = [
                    *messages,
                    {
                        "role": "system",
                        "content": "설명 없이 지정된 교정 JSON 스키마만 반환하세요.",
                    },
                ]
            except AIProviderError as exc:
                if not exc.retryable or attempt + 1 >= total_attempts:
                    raise
            await asyncio.sleep(0.25 * (2**attempt))
        raise AIProviderError(
            "AI_INVALID_RESPONSE", "전문 교정 결과 형식이 올바르지 않습니다.", retryable=True
        )

    async def _request_schema(
        self, messages: list[dict[str, str]], schema_name: str, schema: dict[str, Any]
    ) -> tuple[dict[str, Any], httpx.Response]:
        payload = {
            "model": self.settings.openrouter_analysis_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": self.settings.openrouter_max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.openrouter_timeout_seconds
            ) as client:
                response = await client.post(
                    f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                "AI_TIMEOUT", "AI 응답 시간이 초과되었습니다.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                "AI_CONNECTION_ERROR", "AI 서비스에 연결할 수 없습니다.", retryable=True
            ) from exc
        if response.status_code in {401, 403}:
            raise AIProviderError(
                "AI_AUTHENTICATION_ERROR", "AI 서비스 인증 설정을 확인해 주세요.", retryable=False
            )
        if response.status_code == 429:
            raise AIProviderError(
                "AI_RATE_LIMITED", "AI 요청이 많습니다. 잠시 후 다시 시도해 주세요.", retryable=True
            )
        if response.status_code >= 500:
            raise AIProviderError(
                "AI_SERVICE_UNAVAILABLE",
                "AI 서비스가 일시적으로 응답하지 않습니다.",
                retryable=True,
            )
        if response.status_code >= 400:
            raise AIProviderError(
                "AI_REQUEST_REJECTED", "AI 요청이 거부되었습니다.", retryable=False
            )
        try:
            return response.json(), response
        except ValueError as exc:
            raise AIProviderError(
                "AI_INVALID_RESPONSE", "AI 응답 형식이 올바르지 않습니다.", retryable=True
            ) from exc

    async def _request(self, messages: list[dict[str, str]]) -> AnalysisResult:
        payload = {
            "model": self.settings.openrouter_analysis_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": self.settings.openrouter_max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "meeting_analysis",
                    "strict": True,
                    "schema": MeetingAnalysis.model_json_schema(),
                },
            },
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.openrouter_timeout_seconds
            ) as client:
                response = await client.post(
                    f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                "AI_TIMEOUT", "AI 분석 응답 시간이 초과되었습니다.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                "AI_CONNECTION_ERROR", "AI 서비스에 연결할 수 없습니다.", retryable=True
            ) from exc

        if response.status_code in {401, 403}:
            raise AIProviderError(
                "AI_AUTHENTICATION_ERROR",
                "AI 서비스 인증 설정을 확인해 주세요.",
                retryable=False,
            )
        if response.status_code == 429:
            raise AIProviderError(
                "AI_RATE_LIMITED", "AI 요청이 많습니다. 잠시 후 다시 시도해 주세요.", retryable=True
            )
        if response.status_code >= 500:
            raise AIProviderError(
                "AI_SERVICE_UNAVAILABLE",
                "AI 서비스가 일시적으로 응답하지 않습니다.",
                retryable=True,
            )
        if response.status_code >= 400:
            raise AIProviderError(
                "AI_REQUEST_REJECTED", "AI 분석 요청이 거부되었습니다.", retryable=False
            )

        try:
            body: dict[str, Any] = response.json()
            content = body["choices"][0]["message"]["content"]
            raw_analysis = json.loads(content) if isinstance(content, str) else content
            analysis = MeetingAnalysis.model_validate(raw_analysis)
        except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            raise AIProviderError(
                "AI_INVALID_RESPONSE",
                "AI 분석 결과 형식이 올바르지 않습니다. 다시 시도해 주세요.",
                retryable=True,
            ) from exc

        return AnalysisResult(
            analysis=analysis,
            provider="openrouter",
            model=str(body.get("model") or self.settings.openrouter_analysis_model),
            usage=body.get("usage") if isinstance(body.get("usage"), dict) else {},
            request_id=response.headers.get("x-request-id") or body.get("id"),
        )
