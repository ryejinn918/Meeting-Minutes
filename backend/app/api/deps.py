from functools import lru_cache

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.ai.analysis.base import AnalysisProvider
from app.ai.analysis.mock_provider import MockAnalysisProvider
from app.ai.analysis.openrouter_provider import OpenRouterAnalysisProvider
from app.ai.pipeline import AnalysisService
from app.core.errors import AppError
from app.core.security import AuthenticatedUser, SupabaseTokenVerifier
from app.core.settings import Settings, get_settings
from app.db.ai_repositories import AIRepository
from app.db.client import SupabaseRestClient
from app.db.repositories import MeetFlowRepository

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_token_verifier() -> SupabaseTokenVerifier:
    return SupabaseTokenVerifier(get_settings())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: SupabaseTokenVerifier = Depends(get_token_verifier),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "AUTHENTICATION_REQUIRED", "로그인이 필요합니다.")
    return await verifier.verify(credentials.credentials)


def get_repository(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MeetFlowRepository:
    return MeetFlowRepository(SupabaseRestClient(settings, user.access_token))


def get_admin_repository(settings: Settings = Depends(get_settings)) -> MeetFlowRepository:
    if not settings.supabase_secret_key:
        raise AppError(
            503,
            "SUPABASE_ADMIN_NOT_CONFIGURED",
            "서버의 Supabase 관리 연결이 설정되지 않았습니다.",
        )
    legacy_service_role_token = (
        settings.supabase_secret_key
        if settings.supabase_secret_key.startswith("eyJ")
        else None
    )
    client = SupabaseRestClient(
        settings,
        legacy_service_role_token,
        api_key=settings.supabase_secret_key,
    )
    return MeetFlowRepository(client)


def get_analysis_provider(settings: Settings = Depends(get_settings)) -> AnalysisProvider:
    if settings.ai_mode == "mock":
        if settings.app_env == "production":
            raise AppError(
                503,
                "AI_MOCK_DISABLED",
                "운영 환경에서는 Mock AI 분석을 사용할 수 없습니다.",
            )
        return MockAnalysisProvider()
    if settings.ai_mode == "real":
        return OpenRouterAnalysisProvider(settings)
    raise AppError(503, "AI_MODE_INVALID", "AI 실행 모드 설정을 확인해 주세요.")


def get_analysis_service(
    user: AuthenticatedUser = Depends(get_current_user),
    user_repository: MeetFlowRepository = Depends(get_repository),
    admin_repository: MeetFlowRepository = Depends(get_admin_repository),
    provider: AnalysisProvider = Depends(get_analysis_provider),
    settings: Settings = Depends(get_settings),
) -> AnalysisService:
    return AnalysisService(
        user_repository=user_repository,
        user_ai_repository=AIRepository(user_repository.client),
        admin_repository=admin_repository,
        admin_ai_repository=AIRepository(admin_repository.client),
        user=user,
        provider=provider,
        settings=settings,
    )
