"""SQLite gateway helpers for the runtime knowledge base."""

from collections.abc import Iterator
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

SQLITE_BUSY_TIMEOUT_MS = 30_000


class SQLiteGateway:
    """Lightweight SQLite gateway with serialized write transactions."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._write_lock = RLock()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=NORMAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS model_config (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    llm_model TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    api_key TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    input_mode TEXT NOT NULL,
                    file_type TEXT,
                    storage_path TEXT,
                    strategy TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paragraphs (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    knowledge_type TEXT NOT NULL,
                    token_count INTEGER NOT NULL DEFAULT 0,
                    vector_state TEXT NOT NULL DEFAULT 'pending',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source_id, position),
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    canonical_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    appearance_count INTEGER NOT NULL DEFAULT 1,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    subject_entity_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object_entity_id TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source_paragraph_id TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(subject_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY(object_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY(source_paragraph_id) REFERENCES paragraphs(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS paragraph_entities (
                    id TEXT PRIMARY KEY,
                    paragraph_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    mention_count INTEGER NOT NULL DEFAULT 1,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(paragraph_id, entity_id),
                    FOREIGN KEY(paragraph_id) REFERENCES paragraphs(id) ON DELETE CASCADE,
                    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS paragraph_relations (
                    id TEXT PRIMARY KEY,
                    paragraph_id TEXT NOT NULL,
                    relation_id TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(paragraph_id, relation_id),
                    FOREIGN KEY(paragraph_id) REFERENCES paragraphs(id) ON DELETE CASCADE,
                    FOREIGN KEY(relation_id) REFERENCES relations(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS manual_relations (
                    id TEXT PRIMARY KEY,
                    subject_node_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object_node_id TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS import_jobs (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    input_mode TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    total_files INTEGER NOT NULL DEFAULT 0,
                    completed_files INTEGER NOT NULL DEFAULT 0,
                    failed_files INTEGER NOT NULL DEFAULT 0,
                    total_chunks INTEGER NOT NULL DEFAULT 0,
                    completed_chunks INTEGER NOT NULL DEFAULT 0,
                    failed_chunks INTEGER NOT NULL DEFAULT 0,
                    message TEXT,
                    error TEXT,
                    params TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS import_job_files (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    source_id TEXT,
                    name TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    input_mode TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    total_chunks INTEGER NOT NULL DEFAULT 0,
                    completed_chunks INTEGER NOT NULL DEFAULT 0,
                    failed_chunks INTEGER NOT NULL DEFAULT 0,
                    storage_path TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES import_jobs(id) ON DELETE CASCADE,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS import_job_chunks (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    paragraph_id TEXT,
                    chunk_index INTEGER NOT NULL,
                    chunk_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    step TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    content_preview TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES import_jobs(id) ON DELETE CASCADE,
                    FOREIGN KEY(file_id) REFERENCES import_job_files(id) ON DELETE CASCADE,
                    FOREIGN KEY(paragraph_id) REFERENCES paragraphs(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS record_rows (
                    id TEXT PRIMARY KEY,
                    paragraph_id TEXT NOT NULL UNIQUE,
                    source_id TEXT NOT NULL,
                    worksheet_name TEXT NOT NULL,
                    worksheet_key TEXT NOT NULL,
                    row_index INTEGER NOT NULL,
                    record_key TEXT NOT NULL,
                    entity_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(paragraph_id) REFERENCES paragraphs(id) ON DELETE CASCADE,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS record_cells (
                    id TEXT PRIMARY KEY,
                    record_row_id TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    normalized_column_name TEXT NOT NULL,
                    cell_value TEXT NOT NULL,
                    normalized_value TEXT NOT NULL,
                    is_indexed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(record_row_id) REFERENCES record_rows(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_paragraphs_source_id ON paragraphs(source_id);
                CREATE INDEX IF NOT EXISTS idx_entities_canonical_name ON entities(canonical_name);
                CREATE INDEX IF NOT EXISTS idx_relations_subject_entity_id ON relations(subject_entity_id);
                CREATE INDEX IF NOT EXISTS idx_relations_object_entity_id ON relations(object_entity_id);
                CREATE INDEX IF NOT EXISTS idx_relations_source_paragraph_id ON relations(source_paragraph_id);
                CREATE INDEX IF NOT EXISTS idx_paragraph_entities_entity_id ON paragraph_entities(entity_id);
                CREATE INDEX IF NOT EXISTS idx_paragraph_entities_paragraph_id ON paragraph_entities(paragraph_id);
                CREATE INDEX IF NOT EXISTS idx_paragraph_relations_relation_id ON paragraph_relations(relation_id);
                CREATE INDEX IF NOT EXISTS idx_record_rows_source_id ON record_rows(source_id);
                CREATE INDEX IF NOT EXISTS idx_record_rows_worksheet_key ON record_rows(worksheet_key);
                CREATE INDEX IF NOT EXISTS idx_record_rows_record_key ON record_rows(record_key);
                CREATE INDEX IF NOT EXISTS idx_record_cells_lookup ON record_cells(normalized_column_name, normalized_value);
                CREATE INDEX IF NOT EXISTS idx_record_cells_row_id ON record_cells(record_row_id);
                """
            )
            connection.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Return a serialized write transaction."""

        with self._write_lock:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(sql, params).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._write_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(sql, params)
            connection.commit()

    def dump_json(self, payload: dict[str, Any] | None) -> str:
        return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)

    def load_json(self, raw_value: str | None) -> dict[str, Any]:
        if not raw_value:
            return {}
        try:
            loaded = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        return connection

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        for field_name in ("metadata", "params"):
            if field_name in payload:
                payload[field_name] = self.load_json(payload[field_name])
        return payload
