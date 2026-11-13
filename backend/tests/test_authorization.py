from uuid import UUID

import pytest

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.services.authorization import AuthorizationService

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
TEAM_ID = UUID("22222222-2222-4222-8222-222222222222")


class MembershipRepository:
    def __init__(self, membership: dict | None) -> None:
        self.membership = membership

    async def get_membership(self, team_id: UUID, user_id: UUID) -> dict | None:
        assert team_id == TEAM_ID
        assert user_id == USER_ID
        return self.membership


def service(membership: dict | None) -> AuthorizationService:
    user = AuthenticatedUser(id=USER_ID, email=None, access_token="token")
    return AuthorizationService(MembershipRepository(membership), user)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_active_team_member_is_allowed() -> None:
    membership = {"team_id": str(TEAM_ID), "user_id": str(USER_ID), "role": "member"}

    assert await service(membership).require_team_member(TEAM_ID) == membership


@pytest.mark.asyncio
async def test_non_member_is_denied() -> None:
    with pytest.raises(AppError) as error:
        await service(None).require_team_member(TEAM_ID)

    assert error.value.status_code == 403
    assert error.value.code == "TEAM_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_read_only_member_cannot_edit_another_users_meeting() -> None:
    authorization = service({"role": "member"})
    meeting = {
        "team_id": str(TEAM_ID),
        "created_by": "33333333-3333-4333-8333-333333333333",
    }

    with pytest.raises(AppError) as error:
        await authorization.require_meeting_manager(meeting)

    assert error.value.code == "MEETING_EDIT_DENIED"


@pytest.mark.asyncio
async def test_non_organization_member_is_denied() -> None:
    repository = MembershipRepository(None)
    authorization = AuthorizationService(
        repository,  # type: ignore[arg-type]
        AuthenticatedUser(id=USER_ID, email=None, access_token="token"),
    )

    async def get_organization_membership(
        organization_id: UUID, user_id: UUID
    ) -> None:
        return None

    repository.get_organization_membership = get_organization_membership  # type: ignore[attr-defined,method-assign]
    with pytest.raises(AppError) as error:
        await authorization.require_organization_member(TEAM_ID)

    assert error.value.code == "ORGANIZATION_ACCESS_DENIED"
