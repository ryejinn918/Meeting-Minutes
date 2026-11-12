from functools import lru_cache

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.ai.analysis.base import AnalysisProvider
from app.ai.analysis.mock_provider import MockAnalysisProvider
from app.ai.analysis.openrouter_provider import OpenRouterAnalysisProvider
from app.ai.pipeline import AnalysisService
from app.ai.stt.base import STTProvider
from app.ai.stt.mock_provider import MockSTTProvider
from app.ai.stt.openai_provider import OpenAISTTProvider
from app.core.errors import AppError
from app.core.security import AuthenticatedUser, SupabaseTokenVerifier
from app.core.settings import Settings, get_settings
from app.db.ai_repositories import AIRepository
from app.db.client import SupabaseRestClient
from app.db.repositories import MeetFlowRepository
from app.services.file_ingestion import FileIngestionService
from app.storage.client import SupabaseStorageClient

bearer_scheme = HTTPBearer(auto_error=False)


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


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
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> MeetFlowRepository:
    return MeetFlowRepository(
        SupabaseRestClient(settings, user.access_token, http_client=http_client)
    )


def get_admin_repository(
    settings: Settings = Depends(get_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> MeetFlowRepository:
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
        http_client=http_client,
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


def get_stt_provider(settings: Settings = Depends(get_settings)) -> STTProvider:
    if settings.stt_mode == "mock":
        if settings.app_env == "production":
            raise AppError(
                503,
                "STT_MOCK_DISABLED",
                "운영 환경에서는 Mock 전사를 사용할 수 없습니다.",
            )
        return MockSTTProvider()
    if settings.stt_mode == "real":
        return OpenAISTTProvider(settings)
    raise AppError(503, "STT_MODE_INVALID", "음성 전사 실행 모드 설정을 확인해 주세요.")


def get_storage_client(
    settings: Settings = Depends(get_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> SupabaseStorageClient:
    if not settings.supabase_secret_key:
        raise AppError(503, "SUPABASE_ADMIN_NOT_CONFIGURED", "파일 저장소 설정을 확인해 주세요.")
    return SupabaseStorageClient(settings, http_client=http_client)


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


def get_file_ingestion_service(
    user: AuthenticatedUser = Depends(get_current_user),
    user_repository: MeetFlowRepository = Depends(get_repository),
    admin_repository: MeetFlowRepository = Depends(get_admin_repository),
    storage: SupabaseStorageClient = Depends(get_storage_client),
    stt_provider: STTProvider = Depends(get_stt_provider),
    settings: Settings = Depends(get_settings),
) -> FileIngestionService:
    return FileIngestionService(
        user_repository=user_repository,
        user_job_repository=AIRepository(user_repository.client),
        admin_repository=admin_repository,
        admin_job_repository=AIRepository(admin_repository.client),
        storage=storage,
        stt_provider=stt_provider,
        user=user,
        settings=settings,
    )
