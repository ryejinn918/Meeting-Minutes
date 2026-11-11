from datetime import date

from app.ai.analysis.base import AnalysisResult
from app.schemas.analysis import (
    AnalysisActionItem,
    AnalysisListItem,
    MeetingAnalysis,
)


class MockAnalysisProvider:
    async def analyze(self, transcript: str, *, meeting_date: date) -> AnalysisResult:
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
            usage={"mock": True, "meeting_date": meeting_date.isoformat()},
        )
