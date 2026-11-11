from uuid import UUID

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository
from app.schemas.teams import TeamDetailResponse, TeamMemberResponse, TeamResponse
from app.services.authorization import AuthorizationService


class TeamService:
    def __init__(self, repository: MeetFlowRepository, user: AuthenticatedUser) -> None:
        self.repository = repository
        self.user = user
        self.authorization = AuthorizationService(repository, user)

    async def create(self, name: str) -> TeamResponse:
        team = await self.repository.create_team(name, self.user.id)
        return TeamResponse(**team, member_count=1, my_role="owner")

    async def list(self) -> list[TeamResponse]:
        memberships = await self.repository.list_memberships(self.user.id)
        result: list[TeamResponse] = []
        for membership in memberships:
            team = membership["teams"]
            members = await self.repository.list_team_members(UUID(team["id"]))
            result.append(
                TeamResponse(**team, member_count=len(members), my_role=membership["role"])
            )
        return result

    async def detail(self, team_id: UUID) -> TeamDetailResponse:
        membership = await self.authorization.require_team_member(team_id)
        team = await self.repository.get_team(team_id)
        if team is None:
            raise AppError(404, "TEAM_NOT_FOUND", "팀을 찾을 수 없습니다.")
        rows = await self.repository.list_team_members(team_id)
        members = [
            TeamMemberResponse(
                id=row["profiles"]["id"],
                name=row["profiles"]["display_name"],
                email=row["profiles"]["email"],
                avatar_url=row["profiles"].get("avatar_url"),
                role=row["role"],
            )
            for row in rows
        ]
        return TeamDetailResponse(
            **team,
            member_count=len(members),
            my_role=membership["role"],
            members=members,
        )
