"""Split route definitions by backend domain."""

from src.api.routes.document_routes import router as document_router
from src.api.routes.graph_routes import router as graph_router
from src.api.routes.model_config_routes import router as model_config_router
from src.api.routes.query_routes import router as query_router
from src.api.routes.system_routes import router as system_router

__all__ = [
    "document_router",
    "graph_router",
    "model_config_router",
    "query_router",
    "system_router",
]
