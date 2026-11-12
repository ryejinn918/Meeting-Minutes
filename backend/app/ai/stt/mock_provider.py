from app.ai.stt.base import TranscriptResult


class MockSTTProvider:
    async def transcribe(
        self, content: bytes, *, filename: str, content_type: str
    ) -> TranscriptResult:
        del content, filename, content_type
        return TranscriptResult(
            text=(
                "[Mock 전사 결과]\n"
                "업로드된 음성의 실제 내용은 외부 API를 호출하지 않아 전사하지 않았습니다. "
                "화면 흐름 검증을 위한 개발용 문장입니다."
            ),
            provider="mock",
            model="mock-stt-v1",
            language="ko",
        )
