from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_repository
from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository
from app.schemas.auth import MeResponse

router = APIRouter()


@router.get("/me", response_model=MeResponse)
async def me(
    user: AuthenticatedUser = Depends(get_current_user),
    repository: MeetFlowRepository = Depends(get_repository),
) -> MeResponse:
    profile = await repository.get_profile(user.id)
    if profile is None:
        raise AppError(404, "PROFILE_NOT_FOUND", "사용자 프로필을 찾을 수 없습니다.")
    return MeResponse(
        id=profile["id"],
        email=profile.get("email") or user.email or "",
        display_name=profile["display_name"],
        avatar_url=profile.get("avatar_url"),
    )
