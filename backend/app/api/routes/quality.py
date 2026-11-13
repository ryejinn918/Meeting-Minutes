from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_quality_service
from app.schemas.quality import (
    GlossaryTermCreate,
    GlossaryTermResponse,
    GlossaryTermUpdate,
    MeetingReviewRequest,
    MeetingReviewResponse,
    MeetingTemplateCreate,
    MeetingTemplateResponse,
    MeetingTemplateUpdate,
    QualityOptionsResponse,
    QuestionAnswer,
    QuestionCreate,
    QuestionResponse,
    SegmentSpeakerUpdate,
    SpeakerEditResponse,
    TranscriptCorrectionResult,
    VoiceProfileRequest,
    VoiceProfileResponse,
)
from app.services.quality import QualityService

router = APIRouter()


@router.get("/teams/{team_id}/quality-options", response_model=QualityOptionsResponse)
async def get_quality_options(
    team_id: UUID, service: QualityService = Depends(get_quality_service)
) -> QualityOptionsResponse:
    return await service.options(team_id)


@router.post("/meeting-templates", response_model=MeetingTemplateResponse, status_code=201)
async def create_template(
    payload: MeetingTemplateCreate, service: QualityService = Depends(get_quality_service)
) -> MeetingTemplateResponse:
    return await service.create_template(payload)


@router.patch("/meeting-templates/{template_id}", response_model=MeetingTemplateResponse)
async def update_template(
    template_id: UUID,
    payload: MeetingTemplateUpdate,
    service: QualityService = Depends(get_quality_service),
) -> MeetingTemplateResponse:
    return await service.update_template(template_id, payload)


@router.delete("/meeting-templates/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID, service: QualityService = Depends(get_quality_service)
) -> Response:
    await service.delete_template(template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/glossary-terms", response_model=GlossaryTermResponse, status_code=201)
async def create_glossary(
    payload: GlossaryTermCreate, service: QualityService = Depends(get_quality_service)
) -> GlossaryTermResponse:
    return await service.create_glossary(payload)


@router.patch("/glossary-terms/{term_id}", response_model=GlossaryTermResponse)
async def update_glossary(
    term_id: UUID,
    payload: GlossaryTermUpdate,
    service: QualityService = Depends(get_quality_service),
) -> GlossaryTermResponse:
    return await service.update_glossary(term_id, payload)


@router.delete("/glossary-terms/{term_id}", status_code=204)
async def delete_glossary(
    term_id: UUID, service: QualityService = Depends(get_quality_service)
) -> Response:
    await service.delete_glossary(term_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/meetings/{meeting_id}/transcript/correct",
    response_model=TranscriptCorrectionResult,
)
async def correct_transcript(
    meeting_id: UUID, service: QualityService = Depends(get_quality_service)
) -> TranscriptCorrectionResult:
    return await service.correct_transcript(meeting_id)


@router.post("/meetings/{meeting_id}/questions", response_model=QuestionResponse, status_code=201)
async def create_question(
    meeting_id: UUID,
    payload: QuestionCreate,
    service: QualityService = Depends(get_quality_service),
) -> QuestionResponse:
    return await service.create_question(meeting_id, payload)


@router.patch("/meetings/{meeting_id}/questions/{question_id}", response_model=QuestionResponse)
async def answer_question(
    meeting_id: UUID,
    question_id: UUID,
    payload: QuestionAnswer,
    service: QualityService = Depends(get_quality_service),
) -> QuestionResponse:
    return await service.answer_question(meeting_id, question_id, payload)


@router.patch(
    "/meetings/{meeting_id}/transcript-segments/{segment_id}/speaker",
    response_model=SpeakerEditResponse,
)
async def edit_segment_speaker(
    meeting_id: UUID,
    segment_id: UUID,
    payload: SegmentSpeakerUpdate,
    service: QualityService = Depends(get_quality_service),
) -> SpeakerEditResponse:
    return await service.edit_segment_speaker(meeting_id, segment_id, payload)


@router.post(
    "/meetings/{meeting_id}/speaker-edits/{batch_id}/undo",
    response_model=SpeakerEditResponse,
)
async def undo_speaker_edit(
    meeting_id: UUID,
    batch_id: UUID,
    service: QualityService = Depends(get_quality_service),
) -> SpeakerEditResponse:
    return await service.undo_speaker_edit(meeting_id, batch_id)


@router.post("/meetings/{meeting_id}/review", response_model=MeetingReviewResponse)
async def review_meeting(
    meeting_id: UUID,
    payload: MeetingReviewRequest,
    service: QualityService = Depends(get_quality_service),
) -> MeetingReviewResponse:
    return await service.review(meeting_id, payload)


@router.put("/teams/{team_id}/voice-profile", response_model=VoiceProfileResponse)
async def register_voice_profile(
    team_id: UUID,
    payload: VoiceProfileRequest,
    service: QualityService = Depends(get_quality_service),
) -> VoiceProfileResponse:
    return await service.register_voice_profile(team_id, payload)
