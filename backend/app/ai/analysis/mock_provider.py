from datetime import date

from app.ai.analysis.base import AnalysisResult, CorrectionResult
from app.schemas.analysis import (
    AnalysisActionItem,
    AnalysisListItem,
    MeetingAnalysis,
)
from app.schemas.quality import TranscriptCorrectionResult


class MockAnalysisProvider:
    async def analyze(
        self,
        transcript: str,
        *,
        meeting_date: date,
        context: dict[str, object] | None = None,
    ) -> AnalysisResult:
        excerpt = " ".join(transcript.split())[:180]
        analysis = MeetingAnalysis(
            summary=f"[Mock 분석] {excerpt}",
            key_discussions=[
                AnalysisListItem(
                    text="저장된 회의 전문을 검토했습니다.",
                    evidence=None,
                )
            ],
            decisions=[],
            action_items=[
                AnalysisActionItem(
                    description="Mock 분석 결과를 실제 연동 전에 검토합니다.",
                    assignee_name=None,
                    due_date=None,
                    status="todo",
                    evidence=None,
                )
            ],
            follow_ups=[],
        )
        return AnalysisResult(
            analysis=analysis,
            provider="mock",
            model="mock/deepseek",
            usage={
                "mock": True,
                "meeting_date": meeting_date.isoformat(),
                "context_supplied": bool(context),
            },
        )

    async def correct_transcript(
        self,
        transcript: str,
        *,
        topic: str,
        glossary: list[dict[str, object]],
    ) -> CorrectionResult:
        corrected = transcript
        for item in glossary:
            preferred = str(item.get("preferred_term") or "")
            candidates = [str(item.get("term") or ""), *[str(v) for v in item.get("aliases", [])]]
            for candidate in candidates:
                if candidate and preferred:
                    corrected = corrected.replace(candidate, preferred)
        return CorrectionResult(
            correction=TranscriptCorrectionResult(
                corrected_text=corrected,
                changes=[],
                uncertainties=[],
            ),
            provider="mock",
            model="mock/deepseek",
            usage={"mock": True, "topic_supplied": bool(topic), "glossary_count": len(glossary)},
        )
