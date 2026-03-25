"""面向关系检索模式的应用服务。"""

from src.kb.storage import RelationSearchStore
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RelationSearchService:
    """查询实体关系并整理成前端消费的结构。"""

    def __init__(self, *, relation_search_store: RelationSearchStore) -> None:
        self.relation_search_store = relation_search_store

    def search_relations(self, *, query: str, limit: int = 20) -> dict[str, list[dict[str, object]]]:
        """按关键词执行关系检索。"""

        rows = self.relation_search_store.search_relations(query=query, limit=limit)
        items = [
            {
                "id": str(row["id"]),
                "subject_id": str(row["subject_entity_id"]),
                "subject_name": str(row["subject_name"]),
                "predicate": str(row["predicate"]),
                "object_id": str(row["object_entity_id"]),
                "object_name": str(row["object_name"]),
                "confidence": float(row.get("confidence") or 0.0),
                "source_paragraph_id": str(row.get("source_paragraph_id") or "") or None,
                "metadata": row.get("metadata", {}),
            }
            for row in rows
        ]
        logger.info("关系检索完成：query_length=%s result_count=%s", len(str(query or "").strip()), len(items))
        return {"items": items}
