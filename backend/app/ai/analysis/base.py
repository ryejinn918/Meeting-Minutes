from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from app.schemas.analysis import MeetingAnalysis
from app.schemas.quality import TranscriptCorrectionResult


@dataclass(frozen=True)
class AnalysisResult:
    analysis: MeetingAnalysis
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None


@dataclass(frozen=True)
class CorrectionResult:
    correction: TranscriptCorrectionResult
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None


class AIProviderError(Exception):
    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable


class AnalysisProvider(Protocol):
    async def analyze(
        self,
        transcript: str,
        *,
        meeting_date: date,
        context: dict[str, Any] | None = None,
    ) -> AnalysisResult: ...

    async def correct_transcript(
        self,
        transcript: str,
        *,
        topic: str,
        glossary: list[dict[str, Any]],
    ) -> CorrectionResult: ...
