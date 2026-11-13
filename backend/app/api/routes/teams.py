from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_current_user, get_repository
from app.core.security import AuthenticatedUser
from app.core.settings import Settings, get_settings
from app.db.repositories import MeetFlowRepository
from app.schemas.invitations import InvitationAcceptResponse, InvitationCreate, InvitationResponse
from app.schemas.teams import TeamCreate, TeamDetailResponse, TeamResponse
from app.services.teams import TeamService

router = APIRouter(prefix="/teams")
invitation_router = APIRouter(prefix="/invitations")


def get_service(
    user: AuthenticatedUser = Depends(get_current_user),
    repository: MeetFlowRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> TeamService:
    return TeamService(repository, user, settings)


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


@router.post("/{team_id}/invitations", response_model=InvitationResponse, status_code=201)
async def create_invitation(
    team_id: UUID, payload: InvitationCreate, service: TeamService = Depends(get_service)
) -> InvitationResponse:
    return await service.create_invitation(team_id, payload)


@router.delete("/{team_id}/invitations/{invitation_id}", status_code=204)
async def cancel_invitation(
    team_id: UUID,
    invitation_id: UUID,
    service: TeamService = Depends(get_service),
) -> Response:
    await service.cancel_invitation(team_id, invitation_id)
    return Response(status_code=204)


@invitation_router.post("/{token}/accept", response_model=InvitationAcceptResponse)
async def accept_invitation(
    token: str, service: TeamService = Depends(get_service)
) -> InvitationAcceptResponse:
    return await service.accept_invitation(token)


@invitation_router.post("/{token}/decline", status_code=204)
async def decline_invitation(
    token: str, service: TeamService = Depends(get_service)
) -> Response:
    await service.decline_invitation(token)
    return Response(status_code=204)
