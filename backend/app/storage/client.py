from typing import Any
from urllib.parse import parse_qs, quote, urljoin, urlparse

import httpx

from app.core.errors import AppError
from app.core.settings import Settings


class SupabaseStorageClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.supabase_storage_url.rstrip("/")
        self.headers = {"apikey": settings.supabase_secret_key}
        if settings.supabase_secret_key.startswith("eyJ"):
            self.headers["Authorization"] = f"Bearer {settings.supabase_secret_key}"

    async def create_signed_upload(self, bucket: str, path: str) -> tuple[str, str]:
        data = await self._request(
            "POST",
            f"object/upload/sign/{quote(bucket, safe='')}/{quote(path, safe='/')}",
            json={},
        )
        if not isinstance(data, dict) or not isinstance(data.get("url"), str):
            raise AppError(502, "STORAGE_RESPONSE_ERROR", "파일 업로드 주소를 만들지 못했습니다.")
        signed_url = urljoin(f"{self.base_url}/", data["url"].lstrip("/"))
        token = parse_qs(urlparse(signed_url).query).get("token", [None])[0]
        if not token:
            raise AppError(
                502, "STORAGE_RESPONSE_ERROR", "파일 업로드 주소를 만들지 못했습니다."
            )
        return signed_url, token

    async def download(self, bucket: str, path: str) -> bytes:
        data = await self._request(
            "GET",
            f"object/{quote(bucket, safe='')}/{quote(path, safe='/')}",
            raw=True,
        )
        if not isinstance(data, bytes):
            raise AppError(502, "STORAGE_RESPONSE_ERROR", "원본 파일을 읽지 못했습니다.")
        return data

    async def delete(self, bucket: str, path: str) -> None:
        await self._request(
            "DELETE",
            f"object/{quote(bucket, safe='')}/{quote(path, safe='/')}",
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}/{path}",
                    headers=self.headers,
                    json=json,
                )
        except httpx.HTTPError as exc:
            raise AppError(503, "STORAGE_UNAVAILABLE", "파일 저장소에 연결할 수 없습니다.") from exc
        if response.status_code >= 400:
            upstream_code: str | None = None
            try:
                body = response.json()
                if isinstance(body, dict):
                    code = body.get("error") or body.get("errorCode") or body.get("code")
                    if isinstance(code, str):
                        upstream_code = code
            except ValueError:
                pass
            details: dict[str, Any] = {
                "operation": method,
                "resource": "storage.object",
                "upstream_status": response.status_code,
            }
            if upstream_code:
                details["upstream_code"] = upstream_code
            raise AppError(
                502,
                "STORAGE_ERROR",
                "파일 저장소 작업을 완료하지 못했습니다.",
                details=details,
            )
        if raw:
            return response.content
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise AppError(
                502, "STORAGE_RESPONSE_ERROR", "파일 저장소 응답을 해석할 수 없습니다."
            ) from exc
