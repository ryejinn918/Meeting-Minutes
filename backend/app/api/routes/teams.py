from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_repository
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository
from app.schemas.teams import TeamCreate, TeamDetailResponse, TeamResponse
from app.services.teams import TeamService

router = APIRouter(prefix="/teams")


def get_service(
    user: AuthenticatedUser = Depends(get_current_user),
    repository: MeetFlowRepository = Depends(get_repository),
) -> TeamService:
    return TeamService(repository, user)


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate, service: TeamService = Depends(get_service)
) -> TeamResponse:
    return await service.create(payload)


@router.get("", response_model=list[TeamResponse])
async def list_teams(service: TeamService = Depends(get_service)) -> list[TeamResponse]:
    return await service.list()


@router.get("/{team_id}", response_model=TeamDetailResponse)
async def get_team(
    team_id: UUID, service: TeamService = Depends(get_service)
) -> TeamDetailResponse:
    return await service.detail(team_id)
