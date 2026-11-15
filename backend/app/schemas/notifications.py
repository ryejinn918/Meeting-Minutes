from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    type: Literal["team_invitation"]
    title: str
    body: str
    data: dict[str, Any]
    read_at: datetime | None = None
    created_at: datetime


class NotificationActionResponse(BaseModel):
    team_id: UUID | None = None
