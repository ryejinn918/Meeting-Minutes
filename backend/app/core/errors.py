from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    error: dict[str, Any] = {
        "code": exc.code,
        "message": exc.message,
        "request_id": request_id,
    }
    if exc.details:
        error["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content={"error": error})
