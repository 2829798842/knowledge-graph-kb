"""面向实体检索模式的应用服务。"""

from typing import Any

from src.kb.storage import EntitySearchStore
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EntitySearchService:
    """查询实体列表并整理成前端消费的结构。"""

    def __init__(self, *, entity_search_store: EntitySearchStore) -> None:
        self.entity_search_store = entity_search_store

    def search_entities(self, *, query: str, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        """按名称或描述执行实体检索。"""

        rows = self.entity_search_store.search_entities(query=query, limit=limit)
        items: list[dict[str, Any]] = []
        for row in rows:
            paragraph_ids = [value for value in str(row.get("paragraph_ids") or "").split(",") if value]
            items.append(
                {
                    "id": str(row["id"]),
                    "display_name": str(row["display_name"]),
                    "description": str(row.get("description") or "") or None,
                    "appearance_count": int(row.get("appearance_count") or 0),
                    "metadata": row.get("metadata", {}),
                    "paragraph_ids": paragraph_ids,
                }
            )
        logger.info("实体检索完成：query_length=%s result_count=%s", len(str(query or "").strip()), len(items))
        return {"items": items}
