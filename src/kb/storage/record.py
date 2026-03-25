"""Record store."""

from collections import defaultdict
from typing import Any
from uuid import uuid4

from src.kb.importing.excel import normalize_column_name, normalize_sheet_name

from ..database.sqlite import SQLiteGateway
from .common import placeholders, utc_now_iso


class RecordStore:
    """持久化并读取结构化表格行记录。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def sync_rows_for_paragraphs(self, paragraphs: list[dict[str, Any]]) -> None:
        now = utc_now_iso()
        with self.gateway.transaction() as connection:
            for paragraph in paragraphs:
                metadata = dict(paragraph.get("metadata", {}))
                if str(metadata.get("paragraph_kind") or "") != "row_record":
                    continue
                worksheet_name = str(metadata.get("worksheet_name") or "")
                payload = {
                    "id": str(uuid4()),
                    "paragraph_id": str(paragraph["id"]),
                    "source_id": str(paragraph["source_id"]),
                    "worksheet_name": worksheet_name,
                    "worksheet_key": normalize_sheet_name(worksheet_name),
                    "row_index": int(metadata.get("row_index") or 0),
                    "record_key": str(metadata.get("record_key") or ""),
                    "entity_name": str(metadata.get("record_entity") or ""),
                    "content": str(paragraph["content"]),
                    "metadata": {
                        "primary_key": metadata.get("primary_key"),
                        "headers": metadata.get("headers", []),
                        "header_keys": metadata.get("header_keys", []),
                        "indexed_columns": metadata.get("indexed_columns", []),
                    },
                    "created_at": now,
                    "updated_at": now,
                }
                connection.execute(
                    """
                    INSERT INTO record_rows (
                        id, paragraph_id, source_id, worksheet_name, worksheet_key, row_index,
                        record_key, entity_name, content, metadata, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(paragraph_id) DO UPDATE SET
                        worksheet_name = excluded.worksheet_name,
                        worksheet_key = excluded.worksheet_key,
                        row_index = excluded.row_index,
                        record_key = excluded.record_key,
                        entity_name = excluded.entity_name,
                        content = excluded.content,
                        metadata = excluded.metadata,
                        updated_at = excluded.updated_at
                    """,
                    (
                        payload["id"],
                        payload["paragraph_id"],
                        payload["source_id"],
                        payload["worksheet_name"],
                        payload["worksheet_key"],
                        payload["row_index"],
                        payload["record_key"],
                        payload["entity_name"],
                        payload["content"],
                        self.gateway.dump_json(payload["metadata"]),
                        payload["created_at"],
                        payload["updated_at"],
                    ),
                )
                persisted = connection.execute(
                    "SELECT id FROM record_rows WHERE paragraph_id = ?",
                    (payload["paragraph_id"],),
                ).fetchone()
                record_row_id = str(persisted["id"])
                connection.execute("DELETE FROM record_cells WHERE record_row_id = ?", (record_row_id,))
                indexed_columns = {
                    normalize_column_name(str(value))
                    for value in list(metadata.get("indexed_columns") or [])
                    if normalize_column_name(str(value))
                }
                display_cells = dict(metadata.get("cells") or {})
                normalized_cells = dict(metadata.get("normalized_cells") or {})
                for display_name, cell_value in display_cells.items():
                    column_key = normalize_column_name(display_name)
                    normalized_value = normalize_column_name(str(normalized_cells.get(column_key) or cell_value))
                    if not column_key or not normalized_value:
                        continue
                    connection.execute(
                        """
                        INSERT INTO record_cells (
                            id, record_row_id, column_name, normalized_column_name, cell_value,
                            normalized_value, is_indexed, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid4()),
                            record_row_id,
                            str(display_name),
                            column_key,
                            str(cell_value),
                            normalized_value,
                            1 if column_key in indexed_columns else 0,
                            now,
                            now,
                        ),
                    )
            connection.commit()

    def list_candidate_rows(
        self,
        *,
        source_ids: list[str] | None = None,
        worksheet_names: list[str] | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if source_ids:
            clauses.append(f"record_rows.source_id IN ({placeholders(source_ids)})")
            params.extend(source_ids)
        normalized_sheet_names = [
            normalize_sheet_name(name)
            for name in (worksheet_names or [])
            if normalize_sheet_name(str(name))
        ]
        if normalized_sheet_names:
            clauses.append(f"record_rows.worksheet_key IN ({placeholders(normalized_sheet_names)})")
            params.extend(normalized_sheet_names)
        normalized_filters = {
            normalize_column_name(key): normalize_column_name(value)
            for key, value in dict(filters or {}).items()
            if normalize_column_name(key) and normalize_column_name(value)
        }
        if normalized_filters:
            filter_clauses: list[str] = []
            filter_params: list[Any] = []
            for column_name, normalized_value in normalized_filters.items():
                filter_clauses.append("(normalized_column_name = ? AND normalized_value = ?)")
                filter_params.extend([column_name, normalized_value])
            clauses.append(
                f"""
                record_rows.id IN (
                    SELECT record_row_id
                    FROM record_cells
                    WHERE {" OR ".join(filter_clauses)}
                    GROUP BY record_row_id
                    HAVING COUNT(DISTINCT normalized_column_name) >= {len(normalized_filters)}
                )
                """
            )
            params.extend(filter_params)
        return self.gateway.fetch_all(
            f"""
            SELECT record_rows.*, sources.name AS source_name
            FROM record_rows
            JOIN sources ON sources.id = record_rows.source_id
            WHERE {' AND '.join(clauses)}
            ORDER BY record_rows.worksheet_name ASC, record_rows.row_index ASC
            """,
            tuple(params),
        )

    def list_cells(self, record_row_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not record_row_ids:
            return {}
        rows = self.gateway.fetch_all(
            f"""
            SELECT *
            FROM record_cells
            WHERE record_row_id IN ({placeholders(record_row_ids)})
            ORDER BY column_name ASC
            """,
            tuple(record_row_ids),
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["record_row_id"])].append(row)
        return grouped





