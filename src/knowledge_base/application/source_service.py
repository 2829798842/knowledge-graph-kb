"""来源列表与详情视图的应用服务。"""

from typing import Any

from src.knowledge_base.infrastructure import SearchRepository, SourceRepository


class SourceService:
    """列出来源并解析来源详情。"""

    def __init__(self, *, source_repository: SourceRepository, search_repository: SearchRepository) -> None:
        self.source_repository = source_repository
        self.search_repository = search_repository

    def list_sources(self, *, keyword: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """按关键字列出来源。"""

        return self.source_repository.list_sources(limit=limit, keyword=keyword)

    def get_source_detail(self, source_id: str) -> dict[str, Any] | None:
        """读取单个来源的统计与详情信息。"""

        detail = self.search_repository.get_source_detail(source_id)
        if detail is None:
            return None
        return {
            "source": {
                "id": str(detail["id"]),
                "name": str(detail["name"]),
                "source_kind": str(detail["source_kind"]),
                "input_mode": str(detail["input_mode"]),
                "file_type": detail.get("file_type"),
                "storage_path": detail.get("storage_path"),
                "strategy": str(detail["strategy"]),
                "status": str(detail["status"]),
                "summary": str(detail.get("summary") or "") or None,
                "metadata": detail.get("metadata", {}),
                "created_at": str(detail["created_at"]),
                "updated_at": str(detail["updated_at"]),
            },
            "paragraph_count": int(detail.get("paragraph_count") or 0),
            "entity_count": int(detail.get("entity_count") or 0),
            "relation_count": int(detail.get("relation_count") or 0),
        }

    def list_source_paragraphs(self, source_id: str) -> list[dict[str, Any]] | None:
        """列出指定来源下的全部段落。"""

        source = self.source_repository.get_source(source_id)
        if source is None:
            return None
        return self.source_repository.list_source_paragraphs(source_id)
