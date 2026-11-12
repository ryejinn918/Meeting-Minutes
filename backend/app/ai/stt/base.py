from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    provider: str
    model: str
    language: str | None = None
    request_id: str | None = None


class STTProviderError(Exception):
    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable


class STTProvider(Protocol):
    async def transcribe(
        self, content: bytes, *, filename: str, content_type: str
    ) -> TranscriptResult: ...
