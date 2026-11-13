import hashlib
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.core.settings import Settings
from app.schemas.sharing import MeetingShareItem
from app.services.teams import TeamService

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
TEAM_ID = UUID("22222222-2222-4222-8222-222222222222")


class InvitationRepository:
    def __init__(self, role: str = "owner") -> None:
        self.role = role
        self.cancelled: tuple[UUID, UUID] | None = None
        self.declined_hash: str | None = None

    async def get_membership(self, team_id: UUID, user_id: UUID) -> dict:
        assert team_id == TEAM_ID
        assert user_id == USER_ID
        return {"role": self.role}

    async def cancel_invitation(self, team_id: UUID, invitation_id: UUID) -> bool:
        self.cancelled = (team_id, invitation_id)
        return True

    async def decline_invitation(self, token_hash: str) -> bool:
        self.declined_hash = token_hash
        return True


def service(repository: InvitationRepository) -> TeamService:
    return TeamService(
        repository,  # type: ignore[arg-type]
        AuthenticatedUser(id=USER_ID, email="member@example.com", access_token="token"),
        Settings(_env_file=None),
    )


@pytest.mark.asyncio
async def test_team_manager_can_cancel_active_invitation() -> None:
    repository = InvitationRepository()
    invitation_id = uuid4()

    await service(repository).cancel_invitation(TEAM_ID, invitation_id)

    assert repository.cancelled == (TEAM_ID, invitation_id)


@pytest.mark.asyncio
async def test_regular_member_cannot_cancel_invitation() -> None:
    repository = InvitationRepository(role="member")

    with pytest.raises(AppError) as caught:
        await service(repository).cancel_invitation(TEAM_ID, uuid4())

    assert caught.value.code == "TEAM_MANAGER_REQUIRED"
    assert repository.cancelled is None


@pytest.mark.asyncio
async def test_invitation_decline_hashes_raw_token() -> None:
    repository = InvitationRepository()
    token = "test-invitation-token-with-enough-entropy"

    await service(repository).decline_invitation(token)

    assert repository.declined_hash == hashlib.sha256(token.encode()).hexdigest()


def test_meeting_share_remains_read_only() -> None:
    with pytest.raises(ValidationError):
        MeetingShareItem(user_id=USER_ID, can_edit=True)


def test_phase_c_invitation_rpcs_enforce_terminal_states_and_email() -> None:
    sql = Path(
        "../supabase/migrations/202611130002_phase_c_gpu_worker_collaboration.sql"
    ).read_text(encoding="utf-8").lower()

    assert "create or replace function public.cancel_team_invitation" in sql
    assert "create or replace function public.decline_team_invitation" in sql
    assert "email_normalized=target_email" in sql
    assert "accepted_at is null and declined_at is null and cancelled_at is null" in sql
    assert "expires_at > now()" in sql
    assert "organization membership inactive" in sql
    assert "department membership inactive" in sql
    assert "create or replace function private.cancel_expired_team_invitation" in sql
    assert "and expires_at <= now()" in sql
    assert "team_invitations_cancel_expired_before_insert" in sql
