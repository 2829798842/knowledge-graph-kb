"""Graph store."""

from typing import Any
from uuid import uuid4

from ..database.sqlite import SQLiteGateway
from .common import normalize_entity_name, placeholders, utc_now_iso


class GraphStore:
    """持久化图谱实体、关系，并提供图谱读取能力。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def upsert_entity(
        self,
        *,
        display_name: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        canonical_name = normalize_entity_name(display_name)
        now = utc_now_iso()
        with self.gateway.transaction() as connection:
            existing_row = connection.execute(
                "SELECT * FROM entities WHERE canonical_name = ?",
                (canonical_name,),
            ).fetchone()
            if existing_row is None:
                payload = {
                    "id": str(uuid4()),
                    "display_name": display_name.strip(),
                    "canonical_name": canonical_name,
                    "description": description.strip(),
                    "appearance_count": 1,
                    "metadata": metadata or {},
                    "created_at": now,
                    "updated_at": now,
                }
                connection.execute(
                    """
                    INSERT INTO entities (
                        id, display_name, canonical_name, description, appearance_count,
                        metadata, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["id"],
                        payload["display_name"],
                        payload["canonical_name"],
                        payload["description"],
                        payload["appearance_count"],
                        self.gateway.dump_json(payload["metadata"]),
                        payload["created_at"],
                        payload["updated_at"],
                    ),
                )
                connection.commit()
                return payload

            payload = dict(existing_row)
            next_description = description.strip()
            current_description = str(payload.get("description") or "").strip()
            merged_description = next_description if len(next_description) > len(current_description) else current_description
            merged_metadata = {**self.gateway.load_json(payload.get("metadata")), **(metadata or {})}
            connection.execute(
                """
                UPDATE entities
                SET display_name = ?, description = ?, appearance_count = appearance_count + 1,
                    metadata = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    display_name.strip() or str(payload["display_name"]),
                    merged_description,
                    self.gateway.dump_json(merged_metadata),
                    now,
                    payload["id"],
                ),
            )
            connection.commit()
        return self.get_entity(str(payload["id"])) or {}

    def create_relation(
        self,
        *,
        subject_entity_id: str,
        predicate: str,
        object_entity_id: str,
        confidence: float,
        source_paragraph_id: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        relation_id = str(uuid4())
        now = utc_now_iso()
        payload = {
            "id": relation_id,
            "subject_entity_id": subject_entity_id,
            "predicate": predicate,
            "object_entity_id": object_entity_id,
            "confidence": confidence,
            "source_paragraph_id": source_paragraph_id,
            "metadata": metadata,
            "created_at": now,
            "updated_at": now,
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                INSERT INTO relations (
                    id, subject_entity_id, predicate, object_entity_id, confidence,
                    source_paragraph_id, metadata, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["subject_entity_id"],
                    payload["predicate"],
                    payload["object_entity_id"],
                    payload["confidence"],
                    payload["source_paragraph_id"],
                    self.gateway.dump_json(payload["metadata"]),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return payload

    def link_paragraph_entity(
        self,
        *,
        paragraph_id: str,
        entity_id: str,
        mention_count: int,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        row_id = str(uuid4())
        now = utc_now_iso()
        with self.gateway.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM paragraph_entities WHERE paragraph_id = ? AND entity_id = ?",
                (paragraph_id, entity_id),
            ).fetchone()
            if existing is None:
                payload = {
                    "id": row_id,
                    "paragraph_id": paragraph_id,
                    "entity_id": entity_id,
                    "mention_count": mention_count,
                    "metadata": metadata,
                    "created_at": now,
                    "updated_at": now,
                }
                connection.execute(
                    """
                    INSERT INTO paragraph_entities (
                        id, paragraph_id, entity_id, mention_count, metadata, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["id"],
                        payload["paragraph_id"],
                        payload["entity_id"],
                        payload["mention_count"],
                        self.gateway.dump_json(payload["metadata"]),
                        payload["created_at"],
                        payload["updated_at"],
                    ),
                )
                connection.commit()
                return payload

            merged_metadata = {**self.gateway.load_json(existing["metadata"]), **metadata}
            connection.execute(
                """
                UPDATE paragraph_entities
                SET mention_count = ?, metadata = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    max(int(existing["mention_count"] or 0), mention_count),
                    self.gateway.dump_json(merged_metadata),
                    now,
                    existing["id"],
                ),
            )
            connection.commit()
        return self.gateway.fetch_one("SELECT * FROM paragraph_entities WHERE id = ?", (existing["id"],)) or {}

    def link_paragraph_relation(
        self,
        *,
        paragraph_id: str,
        relation_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        row_id = str(uuid4())
        now = utc_now_iso()
        with self.gateway.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM paragraph_relations WHERE paragraph_id = ? AND relation_id = ?",
                (paragraph_id, relation_id),
            ).fetchone()
            if existing is None:
                payload = {
                    "id": row_id,
                    "paragraph_id": paragraph_id,
                    "relation_id": relation_id,
                    "metadata": metadata,
                    "created_at": now,
                    "updated_at": now,
                }
                connection.execute(
                    """
                    INSERT INTO paragraph_relations (
                        id, paragraph_id, relation_id, metadata, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["id"],
                        payload["paragraph_id"],
                        payload["relation_id"],
                        self.gateway.dump_json(payload["metadata"]),
                        payload["created_at"],
                        payload["updated_at"],
                    ),
                )
                connection.commit()
                return payload

            merged_metadata = {**self.gateway.load_json(existing["metadata"]), **metadata}
            connection.execute(
                "UPDATE paragraph_relations SET metadata = ?, updated_at = ? WHERE id = ?",
                (self.gateway.dump_json(merged_metadata), now, existing["id"]),
            )
            connection.commit()
        return self.gateway.fetch_one("SELECT * FROM paragraph_relations WHERE id = ?", (existing["id"],)) or {}

    def create_manual_relation(
        self,
        *,
        subject_node_id: str,
        predicate: str,
        object_node_id: str,
        weight: float,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        relation_id = str(uuid4())
        now = utc_now_iso()
        payload = {
            "id": relation_id,
            "subject_node_id": subject_node_id,
            "predicate": predicate,
            "object_node_id": object_node_id,
            "weight": weight,
            "metadata": metadata,
            "created_at": now,
            "updated_at": now,
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                INSERT INTO manual_relations (
                    id, subject_node_id, predicate, object_node_id, weight, metadata, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["subject_node_id"],
                    payload["predicate"],
                    payload["object_node_id"],
                    payload["weight"],
                    self.gateway.dump_json(payload["metadata"]),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return payload

    def delete_manual_relation(self, relation_id: str) -> bool:
        with self.gateway.transaction() as connection:
            cursor = connection.execute("DELETE FROM manual_relations WHERE id = ?", (relation_id,))
            connection.commit()
        return cursor.rowcount > 0

    def list_manual_relations(self) -> list[dict[str, Any]]:
        return self.gateway.fetch_all("SELECT * FROM manual_relations ORDER BY created_at DESC")

    def get_manual_relation(self, relation_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM manual_relations WHERE id = ?", (relation_id,))

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM entities WHERE id = ?", (entity_id,))

    def get_relation(self, relation_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one(
            """
            SELECT
                relations.*,
                subject_entity.display_name AS subject_name,
                object_entity.display_name AS object_name
            FROM relations
            JOIN entities AS subject_entity ON subject_entity.id = relations.subject_entity_id
            JOIN entities AS object_entity ON object_entity.id = relations.object_entity_id
            WHERE relations.id = ?
            """,
            (relation_id,),
        )

    def list_graph_sources(self, source_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if source_ids:
            return self.gateway.fetch_all(
                f"SELECT * FROM sources WHERE id IN ({placeholders(source_ids)}) ORDER BY created_at DESC",
                tuple(source_ids),
            )
        return self.gateway.fetch_all("SELECT * FROM sources ORDER BY created_at DESC")

    def list_graph_paragraphs(self, source_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if source_ids:
            return self.gateway.fetch_all(
                f"""
                SELECT *
                FROM paragraphs
                WHERE source_id IN ({placeholders(source_ids)})
                ORDER BY source_id, position
                """,
                tuple(source_ids),
            )
        return self.gateway.fetch_all("SELECT * FROM paragraphs ORDER BY source_id, position")

    def list_graph_entities(self, source_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if not source_ids:
            return self.gateway.fetch_all(
                "SELECT * FROM entities ORDER BY appearance_count DESC, display_name ASC",
            )
        return self.gateway.fetch_all(
            f"""
            SELECT DISTINCT entities.*
            FROM entities
            JOIN paragraph_entities ON paragraph_entities.entity_id = entities.id
            JOIN paragraphs ON paragraphs.id = paragraph_entities.paragraph_id
            WHERE paragraphs.source_id IN ({placeholders(source_ids)})
            ORDER BY entities.appearance_count DESC, entities.display_name ASC
            """,
            tuple(source_ids),
        )

    def list_graph_relations(self, source_ids: list[str] | None = None) -> list[dict[str, Any]]:
        base_sql = """
            SELECT
                relations.*,
                subject_entity.display_name AS subject_name,
                object_entity.display_name AS object_name
            FROM relations
            JOIN entities AS subject_entity ON subject_entity.id = relations.subject_entity_id
            JOIN entities AS object_entity ON object_entity.id = relations.object_entity_id
        """
        if source_ids:
            return self.gateway.fetch_all(
                base_sql
                + f"""
                WHERE relations.source_paragraph_id IN (
                    SELECT id FROM paragraphs WHERE source_id IN ({placeholders(source_ids)})
                )
                ORDER BY relations.created_at DESC
                """,
                tuple(source_ids),
            )
        return self.gateway.fetch_all(base_sql + " ORDER BY relations.created_at DESC")

    def list_relations_for_source(self, source_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            """
            SELECT
                relations.*,
                subject_entity.display_name AS subject_name,
                object_entity.display_name AS object_name
            FROM relations
            JOIN entities AS subject_entity ON subject_entity.id = relations.subject_entity_id
            JOIN entities AS object_entity ON object_entity.id = relations.object_entity_id
            JOIN paragraphs ON paragraphs.id = relations.source_paragraph_id
            WHERE paragraphs.source_id = ?
            ORDER BY relations.created_at DESC
            LIMIT ?
            """,
            (source_id, limit),
        )

    def list_relations_for_paragraph(self, paragraph_id: str) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            """
            SELECT
                relations.*,
                subject_entity.display_name AS subject_name,
                object_entity.display_name AS object_name
            FROM relations
            JOIN entities AS subject_entity ON subject_entity.id = relations.subject_entity_id
            JOIN entities AS object_entity ON object_entity.id = relations.object_entity_id
            JOIN paragraph_relations ON paragraph_relations.relation_id = relations.id
            WHERE paragraph_relations.paragraph_id = ?
            ORDER BY relations.created_at DESC
            """,
            (paragraph_id,),
        )

    def list_relations_for_entity(self, entity_id: str, *, limit: int = 24) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            """
            SELECT
                relations.*,
                subject_entity.display_name AS subject_name,
                object_entity.display_name AS object_name
            FROM relations
            JOIN entities AS subject_entity ON subject_entity.id = relations.subject_entity_id
            JOIN entities AS object_entity ON object_entity.id = relations.object_entity_id
            WHERE relations.subject_entity_id = ? OR relations.object_entity_id = ?
            ORDER BY relations.created_at DESC
            LIMIT ?
            """,
            (entity_id, entity_id, limit),
        )

    def list_paragraphs_for_entity(self, entity_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            """
            SELECT paragraphs.*
            FROM paragraphs
            JOIN paragraph_entities ON paragraph_entities.paragraph_id = paragraphs.id
            WHERE paragraph_entities.entity_id = ?
            ORDER BY paragraphs.created_at DESC
            LIMIT ?
            """,
            (entity_id, limit),
        )

    def list_paragraph_entity_links(
        self,
        *,
        paragraph_ids: list[str] | None = None,
        source_ids: list[str] | None = None,
        entity_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if paragraph_ids:
            sql = f"SELECT * FROM paragraph_entities WHERE paragraph_id IN ({placeholders(paragraph_ids)})"
            params: list[str] = list(paragraph_ids)
            if entity_id:
                sql += " AND entity_id = ?"
                params.append(entity_id)
            return self.gateway.fetch_all(sql, tuple(params))
        if source_ids:
            return self.gateway.fetch_all(
                f"""
                SELECT paragraph_entities.*
                FROM paragraph_entities
                JOIN paragraphs ON paragraphs.id = paragraph_entities.paragraph_id
                WHERE paragraphs.source_id IN ({placeholders(source_ids)})
                """,
                tuple(source_ids),
            )
        if entity_id:
            return self.gateway.fetch_all(
                "SELECT * FROM paragraph_entities WHERE entity_id = ?",
                (entity_id,),
            )
        return self.gateway.fetch_all("SELECT * FROM paragraph_entities")

    def list_paragraph_relation_links(
        self,
        *,
        paragraph_ids: list[str] | None = None,
        paragraph_id: str | None = None,
        relation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if paragraph_ids:
            sql = f"SELECT * FROM paragraph_relations WHERE paragraph_id IN ({placeholders(paragraph_ids)})"
            params: list[str] = list(paragraph_ids)
            if relation_id:
                sql += " AND relation_id = ?"
                params.append(relation_id)
            return self.gateway.fetch_all(sql, tuple(params))
        if paragraph_id and relation_id:
            return self.gateway.fetch_all(
                "SELECT * FROM paragraph_relations WHERE paragraph_id = ? AND relation_id = ?",
                (paragraph_id, relation_id),
            )
        if paragraph_id:
            return self.gateway.fetch_all(
                "SELECT * FROM paragraph_relations WHERE paragraph_id = ?",
                (paragraph_id,),
            )
        if relation_id:
            return self.gateway.fetch_all(
                "SELECT * FROM paragraph_relations WHERE relation_id = ?",
                (relation_id,),
            )
        return self.gateway.fetch_all("SELECT * FROM paragraph_relations")




