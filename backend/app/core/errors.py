from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.shared.error_codes import ErrorCode


class AppError(Exception):
    def __init__(self, code: ErrorCode, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _envelope(code: str, message: str, details: dict) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code.value, exc.message, exc.details))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_envelope(ErrorCode.VALIDATION_ERROR.value, "Invalid request", {"errors": exc.errors()}),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope(ErrorCode.INTERNAL_ERROR.value, "Internal server error", {}),
    )
