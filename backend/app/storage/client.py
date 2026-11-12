import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urljoin, urlparse

import httpx

from app.core.errors import AppError
from app.core.settings import Settings


class SupabaseStorageClient:
    def __init__(
        self, settings: Settings, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self.base_url = settings.supabase_storage_url.rstrip("/")
        self.http_client = http_client
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

    async def download_to_path(
        self,
        bucket: str,
        path: str,
        destination: Path,
        *,
        max_bytes: int,
    ) -> int:
        url = (
            f"{self.base_url}/object/{quote(bucket, safe='')}/"
            f"{quote(path, safe='/')}"
        )
        downloaded = 0
        try:
            client = self.http_client or httpx.AsyncClient()
            try:
                async with client.stream(
                    "GET", url, headers=self.headers, timeout=60
                ) as response:
                    if response.status_code >= 400:
                        details: dict[str, Any] = {
                            "operation": "GET",
                            "resource": "storage.object",
                            "upstream_status": response.status_code,
                        }
                        raise AppError(
                            502,
                            "STORAGE_ERROR",
                            "파일 저장소 작업을 완료하지 못했습니다.",
                            details=details,
                        )
                    with destination.open("wb") as handle:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            downloaded += len(chunk)
                            if downloaded > max_bytes:
                                raise AppError(
                                    413,
                                    "FILE_TOO_LARGE",
                                    "업로드된 파일이 허용된 크기를 초과했습니다.",
                                )
                            await asyncio.to_thread(handle.write, chunk)
            finally:
                if self.http_client is None:
                    await client.aclose()
        except AppError:
            raise
        except httpx.HTTPError as exc:
            raise AppError(
                503,
                "STORAGE_UNAVAILABLE",
                "파일 저장소에 연결할 수 없습니다.",
            ) from exc
        return downloaded

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
            request = {
                "method": method,
                "url": f"{self.base_url}/{path}",
                "headers": self.headers,
                "json": json,
                "timeout": 30,
            }
            if self.http_client is not None:
                response = await self.http_client.request(**request)
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.request(**request)
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
