import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.deps import get_admin_repository, get_storage_client
from app.core.errors import AppError
from app.core.settings import Settings, get_settings
from app.db.repositories import MeetFlowRepository
from app.schemas.worker import (
    WorkerClaimRequest,
    WorkerClaimResponse,
    WorkerCompleteRequest,
    WorkerFailRequest,
    WorkerHeartbeatRequest,
)
from app.services.gpu_worker import GPUWorkerService
from app.storage.client import SupabaseStorageClient

router = APIRouter(prefix="/workers")


def require_worker_token(
    authorization: str | None = Header(default=None), settings: Settings = Depends(get_settings)
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(401, "WORKER_AUTH_REQUIRED", "GPU 워커 인증이 필요합니다.")
    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
    if not settings.gpu_worker_token_hash_list or not any(
        secrets.compare_digest(digest, expected) for expected in settings.gpu_worker_token_hash_list
    ):
        raise AppError(401, "WORKER_AUTH_INVALID", "GPU 워커 인증이 유효하지 않습니다.")


def get_worker_service(
    _: None = Depends(require_worker_token),
    repository: MeetFlowRepository = Depends(get_admin_repository),
    storage: SupabaseStorageClient = Depends(get_storage_client),
    settings: Settings = Depends(get_settings),
) -> GPUWorkerService:
    return GPUWorkerService(repository, storage, settings)


@router.post("/claim", response_model=WorkerClaimResponse)
async def claim(
    payload: WorkerClaimRequest, service: GPUWorkerService = Depends(get_worker_service)
) -> WorkerClaimResponse:
    return WorkerClaimResponse(job=await service.claim(payload.worker_id, payload.worker_name))


@router.post("/jobs/{job_id}/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
async def heartbeat(
    job_id: UUID,
    payload: WorkerHeartbeatRequest,
    service: GPUWorkerService = Depends(get_worker_service),
) -> Response:
    if not await service.heartbeat(job_id, payload.worker_id):
        raise AppError(409, "WORKER_LEASE_INVALID", "작업 소유권이 만료되었습니다.")
    return Response(status_code=204)


@router.post("/jobs/{job_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
async def complete(
    job_id: UUID,
    payload: WorkerCompleteRequest,
    service: GPUWorkerService = Depends(get_worker_service),
) -> Response:
    await service.complete(job_id, payload)
    return Response(status_code=204)


@router.post("/jobs/{job_id}/fail", status_code=status.HTTP_204_NO_CONTENT)
async def fail(
    job_id: UUID,
    payload: WorkerFailRequest,
    service: GPUWorkerService = Depends(get_worker_service),
) -> Response:
    await service.fail(job_id, payload.worker_id, payload.error_code, payload.message)
    return Response(status_code=204)
