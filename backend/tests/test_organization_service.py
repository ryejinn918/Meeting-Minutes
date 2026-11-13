from typing import Any
from uuid import UUID

import pytest

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.schemas.organizations import DepartmentCreate, OrganizationCreate
from app.services.organizations import OrganizationService

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ORGANIZATION_ID = UUID("22222222-2222-4222-8222-222222222222")
DEPARTMENT_ID = UUID("33333333-3333-4333-8333-333333333333")


class OrganizationRepository:
    def __init__(self, role: str | None = "org_admin") -> None:
        self.role = role

    async def create_organization(
        self, name: str, description: str, user_id: UUID
    ) -> dict[str, Any]:
        assert user_id == USER_ID
        return {
            "id": str(ORGANIZATION_ID),
            "name": name,
            "description": description,
            "created_at": "2026-11-12T00:00:00Z",
        }

    async def get_organization_membership(
        self, organization_id: UUID, user_id: UUID
    ) -> dict[str, Any] | None:
        if self.role is None:
            return None
        return {
            "organization_id": str(organization_id),
            "user_id": str(user_id),
            "role": self.role,
        }

    async def create_department(
        self,
        organization_id: UUID,
        name: str,
        description: str,
        user_id: UUID,
    ) -> dict[str, Any]:
        return {
            "id": str(DEPARTMENT_ID),
            "organization_id": str(organization_id),
            "name": name,
            "description": description,
            "created_at": "2026-11-12T00:00:00Z",
        }


def service(repository: OrganizationRepository) -> OrganizationService:
    return OrganizationService(
        repository,  # type: ignore[arg-type]
        AuthenticatedUser(id=USER_ID, email=None, access_token="test"),
    )


@pytest.mark.asyncio
async def test_organization_creator_becomes_admin_response() -> None:
    result = await service(OrganizationRepository()).create(
        OrganizationCreate(name="Example Company")
    )

    assert result.id == ORGANIZATION_ID
    assert result.my_role == "org_admin"


@pytest.mark.asyncio
async def test_only_organization_admin_can_create_department() -> None:
    with pytest.raises(AppError) as error:
        await service(OrganizationRepository(role="member")).create_department(
            ORGANIZATION_ID, DepartmentCreate(name="Product")
        )

    assert error.value.status_code == 403
    assert error.value.code == "ORGANIZATION_ADMIN_REQUIRED"
