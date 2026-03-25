"""重构后知识库运行时使用的 SQLite 仓储实现。"""

from collections import defaultdict
from typing import Any
from uuid import uuid4

from src.knowledge_base.domain import utc_now_iso
from src.knowledge_base.importing.excel import normalize_column_name, normalize_sheet_name

from .sqlite_gateway import SQLiteGateway

DEFAULT_MODEL_CONFIG_ID = "default"


def normalize_entity_name(value: str) -> str:
    return " ".join(str(value).split()).strip().lower()


def _placeholders(values: list[str]) -> str:
    return ", ".join("?" for _ in values)


def _resolve_progress(completed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, min(completed / total, 1.0)) * 100.0, 2)


class ModelConfigRepository:
    """负责运行时模型配置的持久化。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def get(self) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM model_config WHERE id = ?", (DEFAULT_MODEL_CONFIG_ID,))

    def upsert(
        self,
        *,
        provider: str,
        base_url: str,
        llm_model: str,
        embedding_model: str,
        api_key: str | None,
    ) -> dict[str, Any]:
        existing = self.get()
        now = utc_now_iso()
        payload = {
            "id": DEFAULT_MODEL_CONFIG_ID,
            "provider": provider,
            "base_url": base_url,
            "llm_model": llm_model,
            "embedding_model": embedding_model,
            "api_key": api_key,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                INSERT INTO model_config (
                    id, provider, base_url, llm_model, embedding_model, api_key, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    provider = excluded.provider,
                    base_url = excluded.base_url,
                    llm_model = excluded.llm_model,
                    embedding_model = excluded.embedding_model,
                    api_key = excluded.api_key,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["provider"],
                    payload["base_url"],
                    payload["llm_model"],
                    payload["embedding_model"],
                    payload["api_key"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return payload


class ImportJobRepository:
    """负责导入任务、文件与分块的持久化。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def create_job(
        self,
        *,
        source: str,
        input_mode: str,
        strategy: str,
        params: dict[str, Any],
        total_files: int,
    ) -> dict[str, Any]:
        job_id = str(uuid4())
        now = utc_now_iso()
        payload = {
            "id": job_id,
            "source": source,
            "input_mode": input_mode,
            "strategy": strategy,
            "status": "queued",
            "current_step": "queued",
            "progress": 0.0,
            "total_files": total_files,
            "completed_files": 0,
            "failed_files": 0,
            "total_chunks": 0,
            "completed_chunks": 0,
            "failed_chunks": 0,
            "message": "Queued import job",
            "error": None,
            "params": params,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "updated_at": now,
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                INSERT INTO import_jobs (
                    id, source, input_mode, strategy, status, current_step, progress,
                    total_files, completed_files, failed_files, total_chunks, completed_chunks,
                    failed_chunks, message, error, params, created_at, started_at, finished_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["source"],
                    payload["input_mode"],
                    payload["strategy"],
                    payload["status"],
                    payload["current_step"],
                    payload["progress"],
                    payload["total_files"],
                    payload["completed_files"],
                    payload["failed_files"],
                    payload["total_chunks"],
                    payload["completed_chunks"],
                    payload["failed_chunks"],
                    payload["message"],
                    payload["error"],
                    self.gateway.dump_json(payload["params"]),
                    payload["created_at"],
                    payload["started_at"],
                    payload["finished_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return payload

    def create_job_file(
        self,
        *,
        job_id: str,
        name: str,
        source_kind: str,
        input_mode: str,
        strategy: str,
        storage_path: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        file_id = str(uuid4())
        now = utc_now_iso()
        payload = {
            "id": file_id,
            "job_id": job_id,
            "source_id": None,
            "name": name,
            "source_kind": source_kind,
            "input_mode": input_mode,
            "strategy": strategy,
            "status": "queued",
            "current_step": "queued",
            "progress": 0.0,
            "total_chunks": 0,
            "completed_chunks": 0,
            "failed_chunks": 0,
            "storage_path": storage_path,
            "metadata": metadata,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                INSERT INTO import_job_files (
                    id, job_id, source_id, name, source_kind, input_mode, strategy, status,
                    current_step, progress, total_chunks, completed_chunks, failed_chunks,
                    storage_path, metadata, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["job_id"],
                    payload["source_id"],
                    payload["name"],
                    payload["source_kind"],
                    payload["input_mode"],
                    payload["strategy"],
                    payload["status"],
                    payload["current_step"],
                    payload["progress"],
                    payload["total_chunks"],
                    payload["completed_chunks"],
                    payload["failed_chunks"],
                    payload["storage_path"],
                    self.gateway.dump_json(payload["metadata"]),
                    payload["error"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        self.refresh_job_counters(job_id)
        return payload

    def create_job_chunks(
        self,
        *,
        job_id: str,
        file_id: str,
        chunk_previews: list[str],
    ) -> list[dict[str, Any]]:
        now = utc_now_iso()
        rows: list[dict[str, Any]] = []
        with self.gateway.transaction() as connection:
            for chunk_index, preview in enumerate(chunk_previews):
                payload = {
                    "id": str(uuid4()),
                    "job_id": job_id,
                    "file_id": file_id,
                    "paragraph_id": None,
                    "chunk_index": chunk_index,
                    "chunk_type": "paragraph",
                    "status": "queued",
                    "step": "queued",
                    "progress": 0.0,
                    "content_preview": preview[:240] or None,
                    "metadata": {},
                    "error": None,
                    "created_at": now,
                    "updated_at": now,
                }
                connection.execute(
                    """
                    INSERT INTO import_job_chunks (
                        id, job_id, file_id, paragraph_id, chunk_index, chunk_type, status,
                        step, progress, content_preview, metadata, error, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["id"],
                        payload["job_id"],
                        payload["file_id"],
                        payload["paragraph_id"],
                        payload["chunk_index"],
                        payload["chunk_type"],
                        payload["status"],
                        payload["step"],
                        payload["progress"],
                        payload["content_preview"],
                        self.gateway.dump_json(payload["metadata"]),
                        payload["error"],
                        payload["created_at"],
                        payload["updated_at"],
                    ),
                )
                rows.append(payload)
            connection.commit()
        self.refresh_file_counters(file_id)
        return rows

    def list_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            "SELECT * FROM import_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM import_jobs WHERE id = ?", (job_id,))

    def list_job_files(self, job_id: str) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            "SELECT * FROM import_job_files WHERE job_id = ? ORDER BY created_at ASC",
            (job_id,),
        )

    def get_job_file(self, file_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM import_job_files WHERE id = ?", (file_id,))

    def list_job_chunks(self, job_id: str, file_id: str) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            """
            SELECT *
            FROM import_job_chunks
            WHERE job_id = ? AND file_id = ?
            ORDER BY chunk_index ASC
            """,
            (job_id, file_id),
        )

    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        return self._update_row("import_jobs", job_id, fields)

    def update_job_file(self, file_id: str, **fields: Any) -> dict[str, Any] | None:
        row = self._update_row("import_job_files", file_id, fields)
        if row is not None:
            self.refresh_job_counters(str(row["job_id"]))
        return row

    def update_job_chunk(self, chunk_id: str, **fields: Any) -> dict[str, Any] | None:
        row = self._update_row("import_job_chunks", chunk_id, fields)
        if row is not None:
            self.refresh_file_counters(str(row["file_id"]))
        return row

    def refresh_file_counters(self, file_id: str) -> dict[str, Any] | None:
        file_row = self.get_job_file(file_id)
        if file_row is None:
            return None
        with self.gateway.transaction() as connection:
            counters = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_chunks,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_chunks,
                    SUM(CASE WHEN status IN ('failed', 'cancelled', 'aborted') THEN 1 ELSE 0 END) AS failed_chunks
                FROM import_job_chunks
                WHERE file_id = ?
                """,
                (file_id,),
            ).fetchone()
            total_chunks = int(counters["total_chunks"] or 0)
            completed_chunks = int(counters["completed_chunks"] or 0)
            failed_chunks = int(counters["failed_chunks"] or 0)
            progress = _resolve_progress(completed_chunks + failed_chunks, total_chunks)
            connection.execute(
                """
                UPDATE import_job_files
                SET total_chunks = ?, completed_chunks = ?, failed_chunks = ?, progress = ?, updated_at = ?
                WHERE id = ?
                """,
                (total_chunks, completed_chunks, failed_chunks, progress, utc_now_iso(), file_id),
            )
            connection.commit()
        self.refresh_job_counters(str(file_row["job_id"]))
        return self.get_job_file(file_id)

    def refresh_job_counters(self, job_id: str) -> dict[str, Any] | None:
        job_row = self.get_job(job_id)
        if job_row is None:
            return None
        with self.gateway.transaction() as connection:
            file_counters = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_files,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_files,
                    SUM(CASE WHEN status IN ('failed', 'cancelled', 'aborted', 'partial') THEN 1 ELSE 0 END) AS failed_files
                FROM import_job_files
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            chunk_counters = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_chunks,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_chunks,
                    SUM(CASE WHEN status IN ('failed', 'cancelled', 'aborted') THEN 1 ELSE 0 END) AS failed_chunks
                FROM import_job_chunks
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            total_files = int(file_counters["total_files"] or 0)
            completed_files = int(file_counters["completed_files"] or 0)
            failed_files = int(file_counters["failed_files"] or 0)
            total_chunks = int(chunk_counters["total_chunks"] or 0)
            completed_chunks = int(chunk_counters["completed_chunks"] or 0)
            failed_chunks = int(chunk_counters["failed_chunks"] or 0)
            progress = _resolve_progress(
                completed_chunks + failed_chunks if total_chunks else completed_files + failed_files,
                total_chunks if total_chunks else total_files,
            )
            connection.execute(
                """
                UPDATE import_jobs
                SET total_files = ?, completed_files = ?, failed_files = ?,
                    total_chunks = ?, completed_chunks = ?, failed_chunks = ?,
                    progress = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    total_files,
                    completed_files,
                    failed_files,
                    total_chunks,
                    completed_chunks,
                    failed_chunks,
                    progress,
                    utc_now_iso(),
                    job_id,
                ),
            )
            connection.commit()
        return self.get_job(job_id)

    def mark_incomplete_jobs_aborted(self) -> None:
        now = utc_now_iso()
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                UPDATE import_jobs
                SET status = 'aborted',
                    current_step = 'aborted',
                    message = 'Application restarted before job completion.',
                    finished_at = COALESCE(finished_at, ?),
                    updated_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (now, now),
            )
            connection.execute(
                """
                UPDATE import_job_files
                SET status = 'aborted',
                    current_step = 'aborted',
                    updated_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (now,),
            )
            connection.execute(
                """
                UPDATE import_job_chunks
                SET status = 'aborted',
                    step = 'aborted',
                    updated_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (now,),
            )
            connection.commit()

    def hydrate_job(self, job: dict[str, Any]) -> dict[str, Any]:
        files = self.list_job_files(str(job["id"]))
        hydrated_files = [{**file_row, "chunks": self.list_job_chunks(str(job["id"]), str(file_row["id"]))} for file_row in files]
        return {**job, "files": hydrated_files}

    def _update_row(self, table_name: str, row_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        if not fields:
            return self.gateway.fetch_one(f"SELECT * FROM {table_name} WHERE id = ?", (row_id,))
        encoded_fields: dict[str, Any] = {}
        for field_name, value in fields.items():
            if field_name in {"metadata", "params"} and isinstance(value, dict):
                encoded_fields[field_name] = self.gateway.dump_json(value)
            else:
                encoded_fields[field_name] = value
        encoded_fields["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{field_name} = ?" for field_name in encoded_fields)
        params = tuple(encoded_fields.values()) + (row_id,)
        with self.gateway.transaction() as connection:
            connection.execute(
                f"UPDATE {table_name} SET {assignments} WHERE id = ?",
                params,
            )
            connection.commit()
        return self.gateway.fetch_one(f"SELECT * FROM {table_name} WHERE id = ?", (row_id,))


class SourceRepository:
    """负责来源与段落的持久化。"""

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
                    id, name, source_kind, input_mode, file_type, storage_path, strategy, status,
                    summary, metadata, created_at, updated_at
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
            connection.commit()
        return payload

    def update_source(self, source_id: str, **fields: Any) -> dict[str, Any] | None:
        return self._update_row("sources", source_id, fields)

    def add_paragraphs(self, *, source_id: str, paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        now = utc_now_iso()
        with self.gateway.transaction() as connection:
            for position, paragraph in enumerate(paragraphs):
                payload = {
                    "id": str(uuid4()),
                    "source_id": source_id,
                    "position": int(paragraph.get("position", position)),
                    "content": str(paragraph["content"]).strip(),
                    "knowledge_type": str(paragraph.get("knowledge_type", "mixed")),
                    "token_count": int(paragraph.get("token_count", 0)),
                    "vector_state": str(paragraph.get("vector_state", "pending")),
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
                        payload["id"],
                        payload["source_id"],
                        payload["position"],
                        payload["content"],
                        payload["knowledge_type"],
                        payload["token_count"],
                        payload["vector_state"],
                        self.gateway.dump_json(payload["metadata"]),
                        payload["created_at"],
                        payload["updated_at"],
                    ),
                )
                rows.append(payload)
            connection.commit()
        return rows

    def update_paragraph(self, paragraph_id: str, **fields: Any) -> dict[str, Any] | None:
        return self._update_row("paragraphs", paragraph_id, fields)

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM sources WHERE id = ?", (source_id,))

    def list_sources(self, *, limit: int = 100, keyword: str | None = None) -> list[dict[str, Any]]:
        if keyword:
            like_keyword = f"%{keyword.strip()}%"
            return self.gateway.fetch_all(
                """
                SELECT *
                FROM sources
                WHERE name LIKE ? OR summary LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (like_keyword, like_keyword, limit),
            )
        return self.gateway.fetch_all(
            "SELECT * FROM sources ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def list_source_paragraphs(self, source_id: str) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            "SELECT * FROM paragraphs WHERE source_id = ? ORDER BY position ASC",
            (source_id,),
        )

    def get_paragraph(self, paragraph_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM paragraphs WHERE id = ?", (paragraph_id,))

    def delete_source(self, source_id: str) -> bool:
        with self.gateway.transaction() as connection:
            cursor = connection.execute("DELETE FROM sources WHERE id = ?", (source_id,))
            connection.commit()
        return cursor.rowcount > 0

    def _update_row(self, table_name: str, row_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        if not fields:
            return self.gateway.fetch_one(f"SELECT * FROM {table_name} WHERE id = ?", (row_id,))
        encoded_fields: dict[str, Any] = {}
        for field_name, value in fields.items():
            if field_name == "metadata" and isinstance(value, dict):
                encoded_fields[field_name] = self.gateway.dump_json(value)
            else:
                encoded_fields[field_name] = value
        encoded_fields["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{field_name} = ?" for field_name in encoded_fields)
        params = tuple(encoded_fields.values()) + (row_id,)
        with self.gateway.transaction() as connection:
            connection.execute(f"UPDATE {table_name} SET {assignments} WHERE id = ?", params)
            connection.commit()
        return self.gateway.fetch_one(f"SELECT * FROM {table_name} WHERE id = ?", (row_id,))


class GraphRepository:
    """负责图实体、关系以及图查询读模型的持久化。"""

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
                f"SELECT * FROM sources WHERE id IN ({_placeholders(source_ids)}) ORDER BY created_at DESC",
                tuple(source_ids),
            )
        return self.gateway.fetch_all("SELECT * FROM sources ORDER BY created_at DESC")

    def list_graph_paragraphs(self, source_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if source_ids:
            return self.gateway.fetch_all(
                f"""
                SELECT *
                FROM paragraphs
                WHERE source_id IN ({_placeholders(source_ids)})
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
            WHERE paragraphs.source_id IN ({_placeholders(source_ids)})
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
                    SELECT id FROM paragraphs WHERE source_id IN ({_placeholders(source_ids)})
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
            sql = f"SELECT * FROM paragraph_entities WHERE paragraph_id IN ({_placeholders(paragraph_ids)})"
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
                WHERE paragraphs.source_id IN ({_placeholders(source_ids)})
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
            sql = f"SELECT * FROM paragraph_relations WHERE paragraph_id IN ({_placeholders(paragraph_ids)})"
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


class RecordRepository:
    """负责结构化表格行记录的持久化与查询。"""

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
            clauses.append(f"record_rows.source_id IN ({_placeholders(source_ids)})")
            params.extend(source_ids)
        normalized_sheet_names = [
            normalize_sheet_name(name)
            for name in (worksheet_names or [])
            if normalize_sheet_name(str(name))
        ]
        if normalized_sheet_names:
            clauses.append(f"record_rows.worksheet_key IN ({_placeholders(normalized_sheet_names)})")
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
            WHERE record_row_id IN ({_placeholders(record_row_ids)})
            ORDER BY column_name ASC
            """,
            tuple(record_row_ids),
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["record_row_id"])].append(row)
        return grouped


class SearchRepository:
    """为问答、检索与来源详情服务提供读模型。"""

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

    def get_source_detail(self, source_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one(
            """
            SELECT
                sources.*,
                COUNT(DISTINCT paragraphs.id) AS paragraph_count,
                COUNT(DISTINCT paragraph_entities.entity_id) AS entity_count,
                COUNT(DISTINCT relations.id) AS relation_count
            FROM sources
            LEFT JOIN paragraphs ON paragraphs.source_id = sources.id
            LEFT JOIN paragraph_entities ON paragraph_entities.paragraph_id = paragraphs.id
            LEFT JOIN relations ON relations.source_paragraph_id = paragraphs.id
            WHERE sources.id = ?
            GROUP BY sources.id
            """,
            (source_id,),
        )

    def get_paragraphs_with_sources(self, paragraph_ids: list[str]) -> list[dict[str, Any]]:
        if not paragraph_ids:
            return []
        return self.gateway.fetch_all(
            f"""
            SELECT
                paragraphs.*,
                sources.name AS source_name
            FROM paragraphs
            JOIN sources ON sources.id = paragraphs.source_id
            WHERE paragraphs.id IN ({_placeholders(paragraph_ids)})
            ORDER BY paragraphs.position ASC
            """,
            tuple(paragraph_ids),
        )

    def list_entity_links_for_paragraphs(self, paragraph_ids: list[str]) -> list[dict[str, Any]]:
        if not paragraph_ids:
            return []
        return self.gateway.fetch_all(
            f"SELECT * FROM paragraph_entities WHERE paragraph_id IN ({_placeholders(paragraph_ids)})",
            tuple(paragraph_ids),
        )

    def list_relation_links_for_paragraphs(self, paragraph_ids: list[str]) -> list[dict[str, Any]]:
        if not paragraph_ids:
            return []
        return self.gateway.fetch_all(
            f"SELECT * FROM paragraph_relations WHERE paragraph_id IN ({_placeholders(paragraph_ids)})",
            tuple(paragraph_ids),
        )
