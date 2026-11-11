from typing import Any
from uuid import UUID

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository


class AuthorizationService:
    def __init__(self, repository: MeetFlowRepository, user: AuthenticatedUser) -> None:
        self.repository = repository
        self.user = user

    async def require_team_member(self, team_id: UUID) -> dict[str, Any]:
        membership = await self.repository.get_membership(team_id, self.user.id)
        if membership is None:
            raise AppError(403, "TEAM_ACCESS_DENIED", "이 팀에 접근할 권한이 없습니다.")
        return membership

    async def require_meeting_manager(self, meeting: dict[str, Any]) -> None:
        membership = await self.require_team_member(UUID(meeting["team_id"]))
        if meeting["created_by"] != str(self.user.id) and membership["role"] not in {
            "owner",
            "admin",
        }:
            raise AppError(403, "MEETING_EDIT_DENIED", "이 회의록을 수정할 권한이 없습니다.")
