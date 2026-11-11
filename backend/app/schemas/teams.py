from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TeamRole = Literal["owner", "admin", "member"]


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)


class TeamMemberResponse(BaseModel):
    id: UUID
    name: str
    email: str
    avatar_url: str | None = None
    role: TeamRole


class TeamResponse(BaseModel):
    id: UUID
    name: str
    description: str = ""
    member_count: int
    my_role: TeamRole
    created_at: datetime


class TeamDetailResponse(TeamResponse):
    members: list[TeamMemberResponse]
