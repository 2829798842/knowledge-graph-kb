"""导出重构后 API 使用的路由对象。"""

from src.api.routes.kb_graph_routes import router as kb_graph_router
from src.api.routes.kb_import_routes import router as kb_import_router
from src.api.routes.kb_search_routes import router as kb_search_router
from src.api.routes.kb_source_routes import router as kb_source_router
from src.api.routes.model_config_routes import router as model_config_router
from src.api.routes.system_routes import router as system_router

__all__ = [
    "kb_graph_router",
    "kb_import_router",
    "kb_search_router",
    "kb_source_router",
    "model_config_router",
    "system_router",
]
