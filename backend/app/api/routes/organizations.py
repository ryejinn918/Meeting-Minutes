from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_repository
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository
from app.schemas.organizations import (
    DepartmentCreate,
    DepartmentResponse,
    OrganizationCreate,
    OrganizationDetailResponse,
    OrganizationResponse,
)
from app.services.organizations import OrganizationService

router = APIRouter(prefix="/organizations")


def get_service(
    user: AuthenticatedUser = Depends(get_current_user),
    repository: MeetFlowRepository = Depends(get_repository),
) -> OrganizationService:
    return OrganizationService(repository, user)


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    service: OrganizationService = Depends(get_service),
) -> OrganizationResponse:
    return await service.create(payload)


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    service: OrganizationService = Depends(get_service),
) -> list[OrganizationResponse]:
    return await service.list()


@router.get("/{organization_id}", response_model=OrganizationDetailResponse)
async def get_organization(
    organization_id: UUID,
    service: OrganizationService = Depends(get_service),
) -> OrganizationDetailResponse:
    return await service.detail(organization_id)


@router.post(
    "/{organization_id}/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    organization_id: UUID,
    payload: DepartmentCreate,
    service: OrganizationService = Depends(get_service),
) -> DepartmentResponse:
    return await service.create_department(organization_id, payload)
