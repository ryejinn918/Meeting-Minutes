from typing import Any

import httpx

from app.core.errors import AppError
from app.core.settings import Settings


class SupabaseRestClient:
    def __init__(
        self,
        settings: Settings,
        access_token: str | None,
        *,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = settings.supabase_rest_url
        self.http_client = http_client
        self.headers = {
            "apikey": api_key or settings.supabase_publishable_key,
            "Content-Type": "application/json",
        }
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any = None,
        prefer: str | None = None,
    ) -> tuple[Any, httpx.Headers]:
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            request = {
                "method": method,
                "url": f"{self.base_url}/{path.lstrip('/')}",
                "params": params,
                "json": json,
                "headers": headers,
                "timeout": 10,
            }
            if self.http_client is not None:
                response = await self.http_client.request(**request)
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.request(**request)
        except httpx.HTTPError as exc:
            raise AppError(
                503, "DATABASE_UNAVAILABLE", "데이터 저장소에 연결할 수 없습니다."
            ) from exc
        if response.status_code >= 400:
            status = 403 if response.status_code in {401, 403} else 502
            code = "DATABASE_FORBIDDEN" if status == 403 else "DATABASE_ERROR"
            upstream_code: str | None = None
            try:
                error_body = response.json()
                if isinstance(error_body, dict) and isinstance(error_body.get("code"), str):
                    upstream_code = error_body["code"]
            except ValueError:
                pass
            details = {
                "operation": method.upper(),
                "resource": path.strip("/"),
                "upstream_status": response.status_code,
            }
            if upstream_code:
                details["upstream_code"] = upstream_code
            raise AppError(
                status,
                code,
                "요청한 데이터 작업을 완료하지 못했습니다.",
                details=details,
            )
        if response.status_code == 204 or not response.content:
            return None, response.headers
        try:
            return response.json(), response.headers
        except ValueError as exc:
            raise AppError(
                502, "DATABASE_RESPONSE_ERROR", "데이터 응답을 해석할 수 없습니다."
            ) from exc
