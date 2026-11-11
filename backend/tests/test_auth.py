from uuid import UUID

from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_repository
from app.core.security import AuthenticatedUser
from app.main import app

USER_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakeRepository:
    async def get_profile(self, user_id: UUID) -> dict:
        assert user_id == USER_ID
        return {
            "id": str(USER_ID),
            "display_name": "김민지",
            "email": "minji@example.com",
            "avatar_url": None,
        }


def test_protected_endpoint_requires_bearer_token() -> None:
    response = TestClient(app).get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.json()["error"]["request_id"]


def test_analysis_endpoint_requires_bearer_token() -> None:
    response = TestClient(app).post(
        "/api/v1/meetings/33333333-3333-4333-8333-333333333333/process"
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_me_uses_verified_user_dependency() -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=USER_ID, email="minji@example.com", access_token="verified-token"
    )
    app.dependency_overrides[get_repository] = FakeRepository
    try:
        response = TestClient(app).get("/api/v1/me", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == str(USER_ID)
    assert response.json()["display_name"] == "김민지"
