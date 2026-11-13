from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

OrganizationRole = Literal["org_admin", "member"]
DepartmentRole = Literal["department_admin", "member"]


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)


class DepartmentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str = ""
    my_role: DepartmentRole | None = None
    created_at: datetime


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    description: str = ""
    my_role: OrganizationRole
    created_at: datetime


class OrganizationDetailResponse(OrganizationResponse):
    departments: list[DepartmentResponse]
