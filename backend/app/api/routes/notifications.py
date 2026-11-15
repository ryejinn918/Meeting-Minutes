from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_repository
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository
from app.schemas.notifications import NotificationActionResponse, NotificationResponse

router = APIRouter(prefix="/notifications")


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    user: AuthenticatedUser = Depends(get_current_user),
    repository: MeetFlowRepository = Depends(get_repository),
) -> list[NotificationResponse]:
    return [NotificationResponse(**row) for row in await repository.list_notifications(user.id)]


@router.post("/{notification_id}/read", response_model=NotificationActionResponse)
async def mark_read(
    notification_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: MeetFlowRepository = Depends(get_repository),
) -> NotificationActionResponse:
    if not await repository.mark_notification_read(notification_id, user.id):
        return NotificationActionResponse()
    return NotificationActionResponse()


@router.post("/{notification_id}/accept", response_model=NotificationActionResponse)
async def accept(
    notification_id: UUID,
    repository: MeetFlowRepository = Depends(get_repository),
) -> NotificationActionResponse:
    team_id = await repository.accept_invitation_notification(notification_id)
    return NotificationActionResponse(team_id=team_id)


@router.post("/{notification_id}/decline", response_model=NotificationActionResponse)
async def decline(
    notification_id: UUID,
    repository: MeetFlowRepository = Depends(get_repository),
) -> NotificationActionResponse:
    await repository.decline_invitation_notification(notification_id)
    return NotificationActionResponse()
