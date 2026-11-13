from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MeetingShareItem(BaseModel):
    user_id: UUID
    can_edit: Literal[False] = False


class MeetingSharesUpdate(BaseModel):
    shares: list[MeetingShareItem]
