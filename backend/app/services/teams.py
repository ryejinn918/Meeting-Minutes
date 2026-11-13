import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.core.settings import Settings, get_settings
from app.db.repositories import MeetFlowRepository
from app.schemas.invitations import InvitationAcceptResponse, InvitationCreate, InvitationResponse
from app.schemas.teams import TeamCreate, TeamDetailResponse, TeamMemberResponse, TeamResponse
from app.services.authorization import AuthorizationService


class TeamService:
    def __init__(
        self,
        repository: MeetFlowRepository,
        user: AuthenticatedUser,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository
        self.user = user
        self.authorization = AuthorizationService(repository, user)
        self.settings = settings or get_settings()

    async def create_invitation(
        self, team_id: UUID, payload: InvitationCreate
    ) -> InvitationResponse:
        membership = await self.authorization.require_team_member(team_id)
        if membership["role"] not in {"owner", "admin"}:
            raise AppError(403, "TEAM_MANAGER_REQUIRED", "팀 관리자 권한이 필요합니다.")
        token = secrets.token_urlsafe(32)
        invitation = await self.repository.create_invitation(
            {
                "id": str(uuid4()),
                "team_id": str(team_id),
                "email_normalized": payload.email.strip().lower(),
                "role": payload.role,
                "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                "expires_at": (
                    datetime.now(UTC) + timedelta(hours=payload.expires_in_hours)
                ).isoformat(),
                "invited_by": str(self.user.id),
            }
        )
        origin = self.settings.frontend_origin_list[0].rstrip("/")
        return InvitationResponse(
            id=invitation["id"],
            team_id=team_id,
            email=invitation["email_normalized"],
            role=invitation["role"],
            expires_at=invitation["expires_at"],
            accept_url=f"{origin}/invitations/{token}",
        )

    async def accept_invitation(self, token: str) -> InvitationAcceptResponse:
        if len(token) < 20:
            raise AppError(404, "INVITATION_INVALID", "초대 링크가 유효하지 않습니다.")
        team_id = await self.repository.accept_invitation(
            hashlib.sha256(token.encode()).hexdigest()
        )
        return InvitationAcceptResponse(team_id=team_id)

    async def cancel_invitation(self, team_id: UUID, invitation_id: UUID) -> None:
        membership = await self.authorization.require_team_member(team_id)
        if membership["role"] not in {"owner", "admin"}:
            raise AppError(403, "TEAM_MANAGER_REQUIRED", "팀 관리자 권한이 필요합니다.")
        if not await self.repository.cancel_invitation(team_id, invitation_id):
            raise AppError(404, "INVITATION_NOT_ACTIVE", "취소할 수 있는 초대를 찾지 못했습니다.")

    async def decline_invitation(self, token: str) -> None:
        if len(token) < 20:
            raise AppError(404, "INVITATION_INVALID", "초대 링크가 유효하지 않습니다.")
        if not await self.repository.decline_invitation(
            hashlib.sha256(token.encode()).hexdigest()
        ):
            raise AppError(404, "INVITATION_INVALID", "초대 링크가 유효하지 않습니다.")

    async def create(self, payload: TeamCreate) -> TeamResponse:
        if payload.organization_id and payload.department_id:
            organization = await self.authorization.require_organization_member(
                payload.organization_id
            )
            department = await self.repository.get_department(payload.department_id)
            if department is None or department["organization_id"] != str(payload.organization_id):
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
