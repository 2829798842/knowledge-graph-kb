"""来源存储。"""

from typing import Any
from uuid import uuid4

from ..database.sqlite import SQLiteGateway
from .common import utc_now_iso


class SourceStore:
    """负责来源与段落的持久化，并提供来源详情读取能力。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def create_source(
        self,
        *,
        name: str,
        source_kind: str,
        input_mode: str,
        file_type: str | None,
        storage_path: str | None,
        strategy: str,
        status: str,
        summary: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        source_id = str(uuid4())
        now = utc_now_iso()
        payload = {
            "id": source_id,
            "name": name,
            "source_kind": source_kind,
            "input_mode": input_mode,
            "file_type": file_type,
            "storage_path": storage_path,
            "strategy": strategy,
            "status": status,
            "summary": summary,
            "metadata": metadata,
            "created_at": now,
            "updated_at": now,
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                INSERT INTO sources (
                    id, name, source_kind, input_mode, file_type, storage_path, strategy,
                    status, summary, metadata, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["name"],
                    payload["source_kind"],
                    payload["input_mode"],
                    payload["file_type"],
                    payload["storage_path"],
                    payload["strategy"],
                    payload["status"],
                    payload["summary"],
                    self.gateway.dump_json(payload["metadata"]),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
        return payload

    def update_source(
        self,
        source_id: str,
        *,
        name: str | None = None,
        source_kind: str | None = None,
        input_mode: str | None = None,
        file_type: str | None = None,
        storage_path: str | None = None,
        strategy: str | None = None,
        status: str | None = None,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        row = self.get_source(source_id)
        if row is None:
            return None
        payload = {
            "name": row["name"] if name is None else name,
            "source_kind": row["source_kind"] if source_kind is None else source_kind,
            "input_mode": row["input_mode"] if input_mode is None else input_mode,
            "file_type": row["file_type"] if file_type is None else file_type,
            "storage_path": row["storage_path"] if storage_path is None else storage_path,
            "strategy": row["strategy"] if strategy is None else strategy,
            "status": row["status"] if status is None else status,
            "summary": row["summary"] if summary is None else summary,
            "metadata": row["metadata"] if metadata is None else metadata,
            "updated_at": utc_now_iso(),
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                UPDATE sources
                SET name = ?, source_kind = ?, input_mode = ?, file_type = ?, storage_path = ?,
                    strategy = ?, status = ?, summary = ?, metadata = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["name"],
                    payload["source_kind"],
                    payload["input_mode"],
                    payload["file_type"],
                    payload["storage_path"],
                    payload["strategy"],
                    payload["status"],
                    payload["summary"],
                    self.gateway.dump_json(payload["metadata"]),
                    payload["updated_at"],
                    source_id,
                ),
            )
        return self.get_source(source_id)

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM sources WHERE id = ?", (source_id,))

    def list_sources(self, limit: int = 100, keyword: str | None = None) -> list[dict[str, Any]]:
        normalized_keyword = (keyword or "").strip()
        if normalized_keyword:
            like_pattern = f"%{normalized_keyword}%"
            return self.gateway.fetch_all(
                """
                SELECT *
                FROM sources
                WHERE name LIKE ? OR summary LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (like_pattern, like_pattern, limit),
            )

        return self.gateway.fetch_all(
            "SELECT * FROM sources ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )

    def add_paragraphs(self, *, source_id: str, paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = utc_now_iso()
        rows: list[dict[str, Any]] = []
        with self.gateway.transaction() as connection:
            for position, paragraph in enumerate(paragraphs, start=1):
                paragraph_id = str(uuid4())
                row = {
                    "id": paragraph_id,
                    "source_id": source_id,
                    "position": int(paragraph.get("position") or position),
                    "content": str(paragraph["content"]),
                    "knowledge_type": str(paragraph.get("knowledge_type") or "mixed"),
                    "token_count": int(paragraph.get("token_count") or 0),
                    "vector_state": str(paragraph.get("vector_state") or "pending"),
                    "metadata": dict(paragraph.get("metadata", {})),
                    "created_at": now,
                    "updated_at": now,
                }
                connection.execute(
                    """
                    INSERT INTO paragraphs (
                        id, source_id, position, content, knowledge_type, token_count,
                        vector_state, metadata, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["source_id"],
                        row["position"],
                        row["content"],
                        row["knowledge_type"],
                        row["token_count"],
                        row["vector_state"],
                        self.gateway.dump_json(row["metadata"]),
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
                rows.append(row)
        return rows

    def update_paragraph(
        self,
        paragraph_id: str,
        *,
        vector_state: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        row = self.get_paragraph(paragraph_id)
        if row is None:
            return None
        payload = {
            "vector_state": row["vector_state"] if vector_state is None else vector_state,
            "metadata": row["metadata"] if metadata is None else metadata,
            "updated_at": utc_now_iso(),
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                UPDATE paragraphs
                SET vector_state = ?, metadata = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["vector_state"],
                    self.gateway.dump_json(payload["metadata"]),
                    payload["updated_at"],
                    paragraph_id,
                ),
            )
        return self.get_paragraph(paragraph_id)

    def get_paragraph(self, paragraph_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM paragraphs WHERE id = ?", (paragraph_id,))

    def list_paragraphs_for_source(self, source_id: str) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            "SELECT * FROM paragraphs WHERE source_id = ? ORDER BY position ASC",
            (source_id,),
        )

    def list_source_paragraphs(self, source_id: str) -> list[dict[str, Any]]:
        """兼容旧调用的来源段落列表别名。"""

        return self.list_paragraphs_for_source(source_id)

    def get_source_detail(self, source_id: str) -> dict[str, Any] | None:
        source = self.get_source(source_id)
        if source is None:
            return None
        paragraph_count_row = self.gateway.fetch_one(
            "SELECT COUNT(*) AS paragraph_count FROM paragraphs WHERE source_id = ?",
            (source_id,),
        )
        entity_count_row = self.gateway.fetch_one(
            """
            SELECT COUNT(DISTINCT paragraph_entities.entity_id) AS entity_count
            FROM paragraph_entities
            JOIN paragraphs ON paragraphs.id = paragraph_entities.paragraph_id
            WHERE paragraphs.source_id = ?
            """,
            (source_id,),
        )
        relation_count_row = self.gateway.fetch_one(
            """
            SELECT COUNT(DISTINCT paragraph_relations.relation_id) AS relation_count
            FROM paragraph_relations
            JOIN paragraphs ON paragraphs.id = paragraph_relations.paragraph_id
            WHERE paragraphs.source_id = ?
            """,
            (source_id,),
        )
        return {
            "source": source,
            "paragraph_count": int(paragraph_count_row.get("paragraph_count") or 0) if paragraph_count_row else 0,
            "entity_count": int(entity_count_row.get("entity_count") or 0) if entity_count_row else 0,
            "relation_count": int(relation_count_row.get("relation_count") or 0) if relation_count_row else 0,
        }
