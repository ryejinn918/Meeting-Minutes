import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def production_settings(**overrides: str) -> Settings:
    values = {
        "app_env": "production",
        "frontend_origins": "https://meetflow.example",
        "supabase_url": "https://project.supabase.co",
        "supabase_publishable_key": "publishable",
        "supabase_secret_key": "secret",
        "openrouter_api_key": "openrouter",
        "openrouter_analysis_model": "deepseek/model",
        "ai_mode": "real",
        "openai_api_key": "openai",
        "openai_stt_model": "gpt-transcribe",
        "stt_mode": "real",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_production_settings_are_accepted() -> None:
    assert production_settings().app_env == "production"


def test_audio_upload_has_100_mib_hard_cap() -> None:
    with pytest.raises(ValidationError, match="100 MiB"):
        Settings(_env_file=None, max_audio_bytes=104_857_601)


def test_chunk_overlap_must_be_smaller_than_duration() -> None:
    with pytest.raises(ValidationError, match="overlap"):
        Settings(_env_file=None, stt_chunk_seconds=10, stt_chunk_overlap_seconds=10)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"frontend_origins": "*"}, "must not contain"),
        ({"frontend_origins": "http://localhost:5173"}, "HTTPS production origin"),
        ({"ai_mode": "mock"}, "AI_MODE=real"),
        ({"stt_mode": "mock"}, "STT_MODE=real"),
        ({"supabase_secret_key": ""}, "SUPABASE_SECRET_KEY"),
    ],
)
def test_invalid_production_settings_fail_fast(
    overrides: dict[str, str], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        production_settings(**overrides)
