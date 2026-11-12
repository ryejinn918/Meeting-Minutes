from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_current_user, get_repository
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository
from app.schemas.meetings import (
    MeetingCreate,
    MeetingListItemResponse,
    MeetingNotesUpdate,
    MeetingResponse,
    MeetingUpdate,
    TranscriptSpeakerUpdate,
    TranscriptUpsert,
)
from app.services.meetings import MeetingService

router = APIRouter(prefix="/meetings")


def get_service(
    user: AuthenticatedUser = Depends(get_current_user),
    repository: MeetFlowRepository = Depends(get_repository),
) -> MeetingService:
    return MeetingService(repository, user)


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    payload: MeetingCreate, service: MeetingService = Depends(get_service)
) -> MeetingResponse:
    return await service.create(payload)


@router.get("", response_model=list[MeetingListItemResponse])
async def list_meetings(
    team_id: UUID = Query(...), service: MeetingService = Depends(get_service)
) -> list[MeetingListItemResponse]:
    return await service.list(team_id)


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: UUID, service: MeetingService = Depends(get_service)
) -> MeetingResponse:
    return await service.get(meeting_id)


@router.patch("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: UUID, payload: MeetingUpdate, service: MeetingService = Depends(get_service)
) -> MeetingResponse:
    return await service.update(meeting_id, payload)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    meeting_id: UUID, service: MeetingService = Depends(get_service)
) -> Response:
    await service.delete(meeting_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{meeting_id}/transcript", response_model=MeetingResponse)
async def save_transcript(
    meeting_id: UUID,
    payload: TranscriptUpsert,
    service: MeetingService = Depends(get_service),
) -> MeetingResponse:
    return await service.save_transcript(meeting_id, payload.text)


@router.patch(
    "/{meeting_id}/transcript/speakers/{speaker_id}",
    response_model=MeetingResponse,
)
async def update_transcript_speaker(
    meeting_id: UUID,
    speaker_id: UUID,
    payload: TranscriptSpeakerUpdate,
    service: MeetingService = Depends(get_service),
) -> MeetingResponse:
    return await service.update_transcript_speaker(meeting_id, speaker_id, payload)


@router.patch("/{meeting_id}/notes", response_model=MeetingResponse)
async def update_notes(
    meeting_id: UUID,
    payload: MeetingNotesUpdate,
    service: MeetingService = Depends(get_service),
) -> MeetingResponse:
    return await service.update_notes(meeting_id, payload)
