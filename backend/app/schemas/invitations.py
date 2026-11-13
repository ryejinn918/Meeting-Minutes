from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: Literal["admin", "member"] = "member"
    expires_in_hours: int = Field(default=72, ge=1, le=168)


class InvitationResponse(BaseModel):
    id: UUID
    team_id: UUID
    email: str
    role: Literal["admin", "member"]
    expires_at: datetime
    accept_url: str | None = None


class InvitationAcceptResponse(BaseModel):
    team_id: UUID
