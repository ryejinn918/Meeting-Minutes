from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.api.deps import get_file_ingestion_service
from app.schemas.files import (
    FileCompleteResponse,
    MeetingFileResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services.file_ingestion import FileIngestionService

router = APIRouter()


@router.post(
    "/meetings/{meeting_id}/files/upload-url",
    response_model=UploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_url(
    meeting_id: UUID,
    payload: UploadUrlRequest,
    service: FileIngestionService = Depends(get_file_ingestion_service),
) -> UploadUrlResponse:
    return await service.create_upload_url(meeting_id, payload)


@router.post(
    "/meetings/{meeting_id}/files/{file_id}/complete",
    response_model=FileCompleteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_upload(
    meeting_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    service: FileIngestionService = Depends(get_file_ingestion_service),
) -> FileCompleteResponse:
    result = await service.complete(meeting_id, file_id)
    background_tasks.add_task(service.run, result.job_id)
    return result


@router.get("/meetings/{meeting_id}/files", response_model=list[MeetingFileResponse])
async def list_files(
    meeting_id: UUID,
    service: FileIngestionService = Depends(get_file_ingestion_service),
) -> list[MeetingFileResponse]:
    return await service.list_files(meeting_id)
