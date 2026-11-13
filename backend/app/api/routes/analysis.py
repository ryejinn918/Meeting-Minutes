from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.ai.pipeline import AnalysisService
from app.api.deps import get_analysis_service, get_file_ingestion_service
from app.schemas.jobs import JobResponse
from app.services.file_ingestion import FileIngestionService

router = APIRouter()


@router.post(
    "/meetings/{meeting_id}/process",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def process_meeting(
    meeting_id: UUID,
    background_tasks: BackgroundTasks,
    service: AnalysisService = Depends(get_analysis_service),
) -> JobResponse:
    job = await service.start(meeting_id)
    background_tasks.add_task(service.run, job.id)
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    service: AnalysisService = Depends(get_analysis_service),
    file_service: FileIngestionService = Depends(get_file_ingestion_service),
) -> JobResponse:
    job = await service.get_job(job_id)
    if job.job_type == "analyze":
        return job
    return await file_service.get_job(job_id)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    service: AnalysisService = Depends(get_analysis_service),
    file_service: FileIngestionService = Depends(get_file_ingestion_service),
) -> JobResponse:
    current = await service.get_job(job_id)
    if current.job_type == "analyze":
        job = await service.retry(job_id)
        background_tasks.add_task(service.run, job.id)
    else:
        job = await file_service.retry(job_id)
        if file_service.should_run_locally(job):
            background_tasks.add_task(file_service.run, job.id)
    return job
