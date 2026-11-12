from app.ai.stt.base import TranscriptResult, TranscriptSegment


class MockSTTProvider:
    async def transcribe(
        self,
        content: bytes,
        *,
        filename: str,
        content_type: str,
        duration_seconds: float | None = None,
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
            segments=(
                TranscriptSegment(
                    speaker="A",
                    start=0.0,
                    end=4.0,
                    text="업로드된 음성의 개발용 화자 분리 결과입니다.",
                ),
                TranscriptSegment(
                    speaker="B",
                    start=4.0,
                    end=8.0,
                    text="실제 음성 내용은 외부 API를 호출하지 않아 전사하지 않았습니다.",
                ),
            ),
        )
