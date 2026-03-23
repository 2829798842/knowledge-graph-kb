"""模块名称：api.router

主要功能：聚合所有路由并向外提供统一的应用路由入口。
"""

from fastapi import APIRouter

from kb_graph.api.routes.document_routes import router as document_router
from kb_graph.api.routes.graph_routes import router as graph_router
from kb_graph.api.routes.query_routes import router as query_router
from kb_graph.api.routes.system_routes import router as system_router


def create_api_router() -> APIRouter:
    """创建应用总路由。

    Returns:
        APIRouter: 已注册全部子路由的总路由对象。
    """

    router = APIRouter()
    router.include_router(system_router)
    router.include_router(document_router)
    router.include_router(graph_router)
    router.include_router(query_router)
    return router
