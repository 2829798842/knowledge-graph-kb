"""关系检索存储。"""

from typing import Any

from ..database.sqlite import SQLiteGateway


class RelationSearchStore:
    """提供关系搜索模式所需的关系列表查询。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def search_relations(self, *, query: str, limit: int) -> list[dict[str, Any]]:
        like_query = f"%{query.strip()}%"
        return self.gateway.fetch_all(
            """
            SELECT
                relations.*,
                subject_entity.display_name AS subject_name,
                object_entity.display_name AS object_name
            FROM relations
            JOIN entities AS subject_entity ON subject_entity.id = relations.subject_entity_id
            JOIN entities AS object_entity ON object_entity.id = relations.object_entity_id
            WHERE subject_entity.display_name LIKE ?
               OR object_entity.display_name LIKE ?
               OR relations.predicate LIKE ?
            ORDER BY relations.created_at DESC
            LIMIT ?
            """,
            (like_query, like_query, like_query, limit),
        )
