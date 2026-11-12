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
