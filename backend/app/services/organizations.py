from uuid import UUID

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository
from app.schemas.organizations import (
    DepartmentCreate,
    DepartmentResponse,
    OrganizationCreate,
    OrganizationDetailResponse,
    OrganizationResponse,
)
from app.services.authorization import AuthorizationService


class OrganizationService:
    def __init__(self, repository: MeetFlowRepository, user: AuthenticatedUser) -> None:
        self.repository = repository
        self.user = user
        self.authorization = AuthorizationService(repository, user)

    async def create(self, payload: OrganizationCreate) -> OrganizationResponse:
        organization = await self.repository.create_organization(
            payload.name.strip(), payload.description.strip(), self.user.id
        )
        return OrganizationResponse(**organization, my_role="org_admin")

    async def list(self) -> list[OrganizationResponse]:
        memberships = await self.repository.list_organization_memberships(self.user.id)
        return [
            OrganizationResponse(**membership["organizations"], my_role=membership["role"])
            for membership in memberships
        ]

    async def detail(self, organization_id: UUID) -> OrganizationDetailResponse:
        membership = await self.authorization.require_organization_member(organization_id)
        organization = await self.repository.get_organization(organization_id)
        if organization is None:
            raise AppError(404, "ORGANIZATION_NOT_FOUND", "조직을 찾을 수 없습니다.")
        department_memberships = await self.repository.list_department_memberships(
            self.user.id, organization_id
        )
        roles = {row["department_id"]: row["role"] for row in department_memberships}
        departments = await self.repository.list_departments(organization_id)
        return OrganizationDetailResponse(
            **organization,
            my_role=membership["role"],
            departments=[
                DepartmentResponse(**department, my_role=roles.get(department["id"]))
                for department in departments
            ],
        )

    async def create_department(
        self, organization_id: UUID, payload: DepartmentCreate
    ) -> DepartmentResponse:
        await self.authorization.require_organization_admin(organization_id)
        department = await self.repository.create_department(
            organization_id,
            payload.name.strip(),
            payload.description.strip(),
            self.user.id,
        )
        return DepartmentResponse(**department, my_role="department_admin")
