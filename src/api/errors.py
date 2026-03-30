"""API error helpers and application-wide error handlers."""
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


def api_error(*, status_code: int, code: str, message: str) -> HTTPException:
    """Build a structured HTTPException payload."""

    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register consistent JSON error responses for API routes."""

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        payload = _normalize_error_payload(exc.detail, fallback_status=exc.status_code)
        return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "Internal server error.",
            },
        )


def _normalize_error_payload(detail: Any, *, fallback_status: int) -> dict[str, str]:
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("detail") or "").strip()
        code = str(detail.get("code") or "").strip()
        if message:
            return {
                "code": code or _fallback_code(fallback_status),
                "message": message,
            }

    if isinstance(detail, str):
        return {
            "code": _fallback_code(fallback_status),
            "message": detail,
        }

    return {
        "code": _fallback_code(fallback_status),
        "message": "Request failed." if fallback_status < 500 else "Internal server error.",
    }


def _fallback_code(status_code: int) -> str:
    if status_code == 400:
        return "bad_request"
    if status_code == 401:
        return "unauthorized"
    if status_code == 403:
        return "forbidden"
    if status_code == 404:
        return "not_found"
    if status_code == 409:
        return "conflict"
    if status_code == 422:
        return "validation_error"
    if status_code == 503:
        return "service_unavailable"
    if status_code >= 500:
        return "internal_error"
    return f"http_{status_code}"
