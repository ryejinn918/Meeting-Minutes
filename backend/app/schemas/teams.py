from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

TeamRole = Literal["owner", "admin", "member"]


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    organization_id: UUID | None = None
    department_id: UUID | None = None

    @model_validator(mode="after")
    def require_complete_scope(self) -> "TeamCreate":
        if (self.organization_id is None) != (self.department_id is None):
            raise ValueError("조직과 부문을 함께 선택해야 합니다.")
        return self


class TeamScopeResponse(BaseModel):
    id: UUID
    name: str


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
    organization: TeamScopeResponse | None = None
    department: TeamScopeResponse | None = None


class TeamDetailResponse(TeamResponse):
    members: list[TeamMemberResponse]
