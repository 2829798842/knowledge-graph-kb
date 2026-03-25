"""绯荤粺鐩稿叧璺敱銆"""

from fastapi import APIRouter

from src.api.schemas import SystemHealthResponse

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health", response_model=SystemHealthResponse)
def health() -> SystemHealthResponse:
    return SystemHealthResponse()


