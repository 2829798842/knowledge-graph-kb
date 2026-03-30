"""System-level readiness and health routes."""
from fastapi import APIRouter, Depends

from src.api.dependencies import get_maintenance_service
from src.api.schemas import SystemHealthResponse, SystemReadyResponse

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health", response_model=SystemHealthResponse)
def health() -> SystemHealthResponse:
    return SystemHealthResponse()


@router.get("/ready", response_model=SystemReadyResponse)
def ready(maintenance_service=Depends(get_maintenance_service)) -> SystemReadyResponse:
    return SystemReadyResponse(**maintenance_service.ready())
