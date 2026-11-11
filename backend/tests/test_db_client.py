from app.core.settings import Settings
from app.db.client import SupabaseRestClient


def test_user_client_sends_publishable_key_and_user_bearer() -> None:
    settings = Settings(
        _env_file=None,
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="publishable",
    )

    client = SupabaseRestClient(settings, "user-jwt")

    assert client.headers["apikey"] == "publishable"
    assert client.headers["Authorization"] == "Bearer user-jwt"


def test_modern_secret_client_does_not_send_secret_as_bearer() -> None:
    settings = Settings(
        _env_file=None,
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="publishable",
    )

    client = SupabaseRestClient(settings, None, api_key="server-secret")

    assert client.headers["apikey"] == "server-secret"
    assert "Authorization" not in client.headers
