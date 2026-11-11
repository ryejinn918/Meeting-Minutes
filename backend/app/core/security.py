import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import jwt
from jwt import PyJWKSet

from app.core.errors import AppError
from app.core.settings import Settings


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str | None
    access_token: str


class SupabaseTokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwks: dict[str, Any] | None = None
        self._jwks_expires_at = 0.0

    def _ensure_configured(self) -> None:
        if not self.settings.supabase_url or not self.settings.supabase_publishable_key:
            raise AppError(503, "SUPABASE_NOT_CONFIGURED", "Supabase 연결 설정이 필요합니다.")

    async def verify(self, token: str) -> AuthenticatedUser:
        self._ensure_configured()
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AppError(401, "INVALID_TOKEN", "유효하지 않은 인증 토큰입니다.") from exc

        algorithm = header.get("alg")
        mode = self.settings.supabase_jwt_mode
        if mode == "auth_server" or (mode == "auto" and algorithm == "HS256"):
            claims = await self._verify_with_auth_server(token)
        elif mode in {"auto", "jwks"} and algorithm in {"RS256", "ES256", "EdDSA"}:
            claims = await self._verify_with_jwks(token, header)
        else:
            raise AppError(401, "UNSUPPORTED_TOKEN", "지원하지 않는 JWT 서명 방식입니다.")

        try:
            user_id = UUID(str(claims["sub"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(
                401, "INVALID_TOKEN", "인증 토큰의 사용자 정보가 올바르지 않습니다."
            ) from exc
        return AuthenticatedUser(id=user_id, email=claims.get("email"), access_token=token)

    async def _verify_with_jwks(self, token: str, header: dict[str, Any]) -> dict[str, Any]:
        jwks = await self._get_jwks()
        key_id = header.get("kid")
        try:
            key = next(item.key for item in PyJWKSet.from_dict(jwks).keys if item.key_id == key_id)
            return jwt.decode(
                token,
                key,
                algorithms=[str(header["alg"])],
                audience=self.settings.supabase_jwt_audience,
                issuer=self.settings.supabase_issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except (StopIteration, KeyError, jwt.PyJWTError) as exc:
            raise AppError(
                401, "INVALID_TOKEN", "인증 토큰이 만료되었거나 유효하지 않습니다."
            ) from exc

    async def _get_jwks(self) -> dict[str, Any]:
        if self._jwks and time.monotonic() < self._jwks_expires_at:
            return self._jwks
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(self.settings.supabase_jwks_url)
                response.raise_for_status()
                self._jwks = response.json()
                self._jwks_expires_at = time.monotonic() + self.settings.supabase_jwks_cache_seconds
                return self._jwks
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError(
                503, "AUTH_SERVICE_UNAVAILABLE", "인증 서비스를 확인할 수 없습니다."
            ) from exc

    async def _verify_with_auth_server(self, token: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.settings.supabase_issuer}/user",
                    headers={
                        "apikey": self.settings.supabase_publishable_key,
                        "Authorization": f"Bearer {token}",
                    },
                )
            if response.status_code != 200:
                raise AppError(401, "INVALID_TOKEN", "인증 토큰이 만료되었거나 유효하지 않습니다.")
            user = response.json()
            claims = jwt.decode(token, options={"verify_signature": False})
            now = int(time.time())
            audience = claims.get("aud")
            valid_audience = (
                self.settings.supabase_jwt_audience in audience
                if isinstance(audience, list)
                else audience == self.settings.supabase_jwt_audience
            )
            if (
                claims.get("iss") != self.settings.supabase_issuer
                or not valid_audience
                or int(claims.get("exp", 0)) <= now
                or claims.get("sub") != user.get("id")
            ):
                raise AppError(401, "INVALID_TOKEN", "인증 토큰의 필수 정보가 올바르지 않습니다.")
            return claims
        except AppError:
            raise
        except (httpx.HTTPError, ValueError, TypeError, jwt.PyJWTError) as exc:
            raise AppError(
                503, "AUTH_SERVICE_UNAVAILABLE", "인증 서비스를 확인할 수 없습니다."
            ) from exc
