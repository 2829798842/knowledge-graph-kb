"""面向来源检索模式的应用服务。"""

from src.kb.storage import SourceSearchStore
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SourceSearchService:
    """查询来源列表并整理成前端消费的结构。"""

    def __init__(self, *, source_search_store: SourceSearchStore) -> None:
        self.source_search_store = source_search_store

    def search_sources(self, *, query: str, limit: int = 20) -> dict[str, list[dict[str, object]]]:
        """按来源名称、类型或摘要执行检索。"""

        rows = self.source_search_store.search_sources(query=query, limit=limit)
        items = [
            {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "source_kind": str(row["source_kind"]),
                "summary": str(row.get("summary") or "") or None,
                "metadata": row.get("metadata", {}),
                "paragraph_count": int(row.get("paragraph_count") or 0),
            }
            for row in rows
        ]
        logger.info("来源检索完成：query_length=%s result_count=%s", len(str(query or "").strip()), len(items))
        return {"items": items}
