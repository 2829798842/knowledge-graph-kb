"""HTTP API 包。"""

from fastapi import APIRouter


def create_api_router() -> APIRouter:
    """以惰性方式创建聚合后的 API 路由。"""

    from src.api.router import create_api_router as build_router

    return build_router()

__all__ = ["create_api_router"]
