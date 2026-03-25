"""来源检索存储。"""

from typing import Any

from ..database.sqlite import SQLiteGateway


class SourceSearchStore:
    """提供来源搜索模式所需的来源列表与检索查询。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def search_sources(self, *, query: str, limit: int) -> list[dict[str, Any]]:
        like_query = f"%{query.strip()}%"
        return self.gateway.fetch_all(
            """
            SELECT
                sources.*,
                COUNT(paragraphs.id) AS paragraph_count
            FROM sources
            LEFT JOIN paragraphs ON paragraphs.source_id = sources.id
            WHERE sources.name LIKE ? OR sources.summary LIKE ?
            GROUP BY sources.id
            ORDER BY sources.created_at DESC
            LIMIT ?
            """,
            (like_query, like_query, limit),
        )
