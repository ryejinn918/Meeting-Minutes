from uuid import UUID

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository
from app.schemas.teams import TeamCreate, TeamDetailResponse, TeamMemberResponse, TeamResponse
from app.services.authorization import AuthorizationService


class TeamService:
    def __init__(self, repository: MeetFlowRepository, user: AuthenticatedUser) -> None:
        self.repository = repository
        self.user = user
        self.authorization = AuthorizationService(repository, user)

    async def create(self, payload: TeamCreate) -> TeamResponse:
        if payload.organization_id and payload.department_id:
            organization = await self.authorization.require_organization_member(
                payload.organization_id
            )
            department = await self.repository.get_department(payload.department_id)
            if (
                department is None
                or department["organization_id"] != str(payload.organization_id)
            ):
                raise AppError(
                    400,
                    "DEPARTMENT_SCOPE_INVALID",
                    "선택한 부문이 조직에 속하지 않습니다.",
                )
            if organization["role"] != "org_admin":
                await self.authorization.require_department_admin(payload.department_id)
        team = await self.repository.create_team(
            payload.name.strip(),
            self.user.id,
            organization_id=payload.organization_id,
            department_id=payload.department_id,
        )
        return self._response(team, member_count=1, my_role="owner")

    async def list(self) -> list[TeamResponse]:
        memberships = await self.repository.list_memberships(self.user.id)
        counts = await self.repository.count_team_members(
            {UUID(membership["team_id"]) for membership in memberships}
        )
        result: list[TeamResponse] = []
        for membership in memberships:
            team = membership["teams"]
            result.append(
                self._response(
                    team,
                    member_count=counts.get(str(team["id"]), 0),
                    my_role=membership["role"],
                )
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
            **self._response(
                team,
                member_count=len(members),
                my_role=membership["role"],
            ).model_dump(),
            members=members,
        )

    @staticmethod
    def _response(team: dict, *, member_count: int, my_role: str) -> TeamResponse:
        return TeamResponse(
            id=team["id"],
            name=team["name"],
            description=team.get("description", ""),
            created_at=team["created_at"],
            member_count=member_count,
            my_role=my_role,
            organization=team.get("organizations"),
            department=team.get("departments"),
        )
