from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "meetflow-api"
    api_v1_prefix: str = "/api/v1"
    frontend_origins: str = "http://localhost:5173"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_mode: str = "auto"
    supabase_jwks_cache_seconds: int = 600
    supabase_storage_bucket: str = "meeting-files"
    max_audio_bytes: int = 52_428_800
    max_document_bytes: int = 10_485_760
    max_pdf_pages: int = 200
    stt_direct_max_bytes: int = 20_000_000
    stt_chunk_seconds: int = 600
    stt_chunk_overlap_seconds: int = 2
    stt_max_chunks: int = 24
    stt_max_audio_seconds: int = 14_400
    openai_api_key: str = ""
    openai_stt_model: str = "gpt-4o-transcribe-diarize"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 90.0
    openai_max_retries: int = 1
    stt_mode: str = "mock"
    openrouter_api_key: str = ""
    openrouter_analysis_model: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_seconds: float = 45.0
    openrouter_max_retries: int = 1
    openrouter_max_output_tokens: int = 2500
    ai_mode: str = "mock"
    ai_max_transcript_chars: int = 120_000
    ai_stale_job_seconds: int = 300

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        if self.max_audio_bytes > 104_857_600:
            raise ValueError("MAX_AUDIO_BYTES must not exceed 100 MiB")
        if not 0 <= self.stt_chunk_overlap_seconds < self.stt_chunk_seconds:
            raise ValueError("STT chunk overlap must be smaller than the chunk duration")
        if self.app_env != "production":
            return self
        required = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_PUBLISHABLE_KEY": self.supabase_publishable_key,
            "SUPABASE_SECRET_KEY": self.supabase_secret_key,
            "FRONTEND_ORIGINS": self.frontend_origins,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"Missing production settings: {', '.join(missing)}")
        if "*" in self.frontend_origin_list:
            raise ValueError("FRONTEND_ORIGINS must not contain '*' in production")
        if not any(origin.startswith("https://") for origin in self.frontend_origin_list):
            raise ValueError("FRONTEND_ORIGINS must include an HTTPS production origin")
        if self.ai_mode != "real" or not (
            self.openrouter_api_key.strip() and self.openrouter_analysis_model.strip()
        ):
            raise ValueError(
                "Production requires AI_MODE=real, OPENROUTER_API_KEY, and "
                "OPENROUTER_ANALYSIS_MODEL"
            )
        if self.stt_mode != "real" or not (
            self.openai_api_key.strip() and self.openai_stt_model.strip()
        ):
            raise ValueError(
                "Production requires STT_MODE=real, OPENAI_API_KEY, and OPENAI_STT_MODEL"
            )
        return self

    @property
    def frontend_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"

    @property
    def supabase_rest_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/rest/v1"

    @property
    def supabase_storage_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/storage/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
