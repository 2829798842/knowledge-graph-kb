"""来源列表与详情视图的应用服务。"""

from typing import Any

from src.kb.storage import SourceStore


class SourceService:
    """列出来源并组装来源详情数据。"""

    def __init__(self, *, source_store: SourceStore) -> None:
        self.source_store = source_store

    def list_sources(self, *, keyword: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """按关键字列出来源。"""

        return self.source_store.list_sources(limit=limit, keyword=keyword)

    def get_source_detail(self, source_id: str) -> dict[str, Any] | None:
        """读取单个来源的统计与详情信息。"""

        detail = self.source_store.get_source_detail(source_id)
        if detail is None:
            return None
        source = detail["source"]
        return {
            "source": {
                "id": str(source["id"]),
                "name": str(source["name"]),
                "source_kind": str(source["source_kind"]),
                "input_mode": str(source["input_mode"]),
                "file_type": source.get("file_type"),
                "storage_path": source.get("storage_path"),
                "strategy": str(source["strategy"]),
                "status": str(source["status"]),
                "summary": str(source.get("summary") or "") or None,
                "metadata": source.get("metadata", {}),
                "created_at": str(source["created_at"]),
                "updated_at": str(source["updated_at"]),
            },
            "paragraph_count": int(detail.get("paragraph_count") or 0),
            "entity_count": int(detail.get("entity_count") or 0),
            "relation_count": int(detail.get("relation_count") or 0),
        }

    def list_source_paragraphs(self, source_id: str) -> list[dict[str, Any]] | None:
        """列出指定来源下的全部段落。"""

        source = self.source_store.get_source(source_id)
        if source is None:
            return None
        return self.source_store.list_source_paragraphs(source_id)
