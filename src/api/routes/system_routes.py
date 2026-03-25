"""系统相关路由。"""

from fastapi import APIRouter

from src.api.schemas import SystemHealthResponse

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health", response_model=SystemHealthResponse)
def health() -> SystemHealthResponse:
    return SystemHealthResponse()
