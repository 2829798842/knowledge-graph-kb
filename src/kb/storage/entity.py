"""实体检索存储。"""

from typing import Any

from ..database.sqlite import SQLiteGateway


class EntitySearchStore:
    """提供实体检索所需的查询能力。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def search_entities(self, *, query: str, limit: int) -> list[dict[str, Any]]:
        like_query = f"%{query.strip()}%"
        return self.gateway.fetch_all(
            """
            SELECT
                entities.*,
                GROUP_CONCAT(paragraph_entities.paragraph_id) AS paragraph_ids
            FROM entities
            LEFT JOIN paragraph_entities ON paragraph_entities.entity_id = entities.id
            WHERE entities.display_name LIKE ? OR entities.description LIKE ?
            GROUP BY entities.id
            ORDER BY entities.appearance_count DESC, entities.display_name ASC
            LIMIT ?
            """,
            (like_query, like_query, limit),
        )
