"""Import-job store."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from ..database.sqlite import SQLiteGateway
from .common import resolve_progress, utc_now_iso


class ImportJobStore:
    """Persist import jobs, files, and chunk records."""

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
            "message": "导入任务已排队，等待执行。",
            "error": None,
            "params": {
                **params,
                "step_durations": {},
                "step_started_at": now,
                "progress_step": "queued",
                "failure_stage": None,
                "stats": {},
                "retry_of": params.get("retry_of"),
            },
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
            "metadata": {
                **metadata,
                "step_durations": {},
                "step_started_at": now,
                "progress_step": "queued",
                "failure_stage": None,
                "stats": {},
            },
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
        current_row = self.get_job(job_id)
        if current_row is not None:
            fields = self._apply_job_diagnostics(row=current_row, fields=fields)
        return self._update_row("import_jobs", job_id, fields)

    def update_job_file(self, file_id: str, **fields: Any) -> dict[str, Any] | None:
        current_row = self.get_job_file(file_id)
        if current_row is not None:
            fields = self._apply_file_diagnostics(row=current_row, fields=fields)
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
            progress = resolve_progress(completed_chunks + failed_chunks, total_chunks)
            connection.execute(
                """
                UPDATE import_job_files
                SET total_chunks = ?, completed_chunks = ?, failed_chunks = ?, progress = ?, updated_at = ?
                WHERE id = ?
                """,
                (total_chunks, completed_chunks, failed_chunks, progress, utc_now_iso(), file_id),
            )
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
            progress = resolve_progress(
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
        return self.get_job(job_id)

    def mark_incomplete_jobs_aborted(self) -> None:
        now = utc_now_iso()
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                UPDATE import_jobs
                SET status = 'aborted',
                    current_step = 'aborted',
                    message = '应用重启时任务尚未完成，已标记为中止。',
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

    def hydrate_job(self, job: dict[str, Any]) -> dict[str, Any]:
        files = self.list_job_files(str(job["id"]))
        hydrated_files = [
            self._build_file_payload(
                file_row=file_row,
                chunks=self.list_job_chunks(str(job["id"]), str(file_row["id"])),
            )
            for file_row in files
        ]
        return self._build_job_payload(job=job, files=hydrated_files)

    def _build_file_payload(self, *, file_row: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
        metadata = dict(file_row.get("metadata", {}))
        stats = {
            "paragraph_count": int(metadata.get("paragraph_count") or 0),
            "entity_count": int(metadata.get("entity_count") or 0),
            "relation_count": int(metadata.get("relation_count") or 0),
            "total_chunks": int(file_row.get("total_chunks") or 0),
            "completed_chunks": int(file_row.get("completed_chunks") or 0),
            "failed_chunks": int(file_row.get("failed_chunks") or 0),
        }
        failure_stage = metadata.get("failure_stage")
        if not failure_stage and str(file_row.get("status") or "") in {"failed", "partial", "cancelled", "aborted"}:
            failure_stage = str(file_row.get("current_step") or "")
        return {
            **file_row,
            "chunks": chunks,
            "failure_stage": str(failure_stage or "") or None,
            "step_durations": {
                str(key): float(value)
                for key, value in dict(metadata.get("step_durations", {})).items()
                if self._is_number(value)
            },
            "stats": stats,
        }

    def _build_job_payload(self, *, job: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
        params = dict(job.get("params", {}))
        aggregated_step_durations: dict[str, float] = {}
        for file_row in files:
            for step_name, duration in dict(file_row.get("step_durations", {})).items():
                aggregated_step_durations[step_name] = round(
                    aggregated_step_durations.get(step_name, 0.0) + float(duration),
                    3,
                )

        failure_stage = next(
            (str(file_row.get("failure_stage") or "") for file_row in files if str(file_row.get("failure_stage") or "").strip()),
            str(params.get("failure_stage") or ""),
        )
        stats = {
            "total_files": int(job.get("total_files") or 0),
            "completed_files": int(job.get("completed_files") or 0),
            "failed_files": int(job.get("failed_files") or 0),
            "total_chunks": int(job.get("total_chunks") or 0),
            "completed_chunks": int(job.get("completed_chunks") or 0),
            "failed_chunks": int(job.get("failed_chunks") or 0),
            "paragraph_count": sum(int(file_row.get("stats", {}).get("paragraph_count") or 0) for file_row in files),
            "entity_count": sum(int(file_row.get("stats", {}).get("entity_count") or 0) for file_row in files),
            "relation_count": sum(int(file_row.get("stats", {}).get("relation_count") or 0) for file_row in files),
        }
        return {
            **job,
            "files": files,
            "failure_stage": failure_stage or None,
            "step_durations": aggregated_step_durations,
            "retry_of": str(params.get("retry_of") or "") or None,
            "stats": stats,
        }

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
        return self.gateway.fetch_one(f"SELECT * FROM {table_name} WHERE id = ?", (row_id,))

    def _apply_job_diagnostics(self, *, row: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
        next_fields = dict(fields)
        params = dict(row.get("params", {}))
        params.update(dict(next_fields.get("params", {})))
        now = utc_now_iso()
        current_step = str(row.get("current_step") or "")
        next_step = str(next_fields.get("current_step") or current_step or "").strip()
        if "step_started_at" not in params:
            params["step_started_at"] = row.get("started_at") or row.get("created_at") or now
        if "step_durations" not in params:
            params["step_durations"] = {}
        if next_step and next_step != str(params.get("progress_step") or current_step or ""):
            self._finalize_step_duration(payload=params, previous_step=str(params.get("progress_step") or current_step or ""), finished_at=now)
            params["progress_step"] = next_step
            params["step_started_at"] = now
        if str(next_fields.get("status") or row.get("status") or "") in {"failed", "partial", "cancelled", "aborted"}:
            params["failure_stage"] = str(next_fields.get("current_step") or row.get("current_step") or next_step or "") or None
        next_fields["params"] = params
        return next_fields

    def _apply_file_diagnostics(self, *, row: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
        next_fields = dict(fields)
        metadata = dict(row.get("metadata", {}))
        metadata.update(dict(next_fields.get("metadata", {})))
        now = utc_now_iso()
        current_step = str(row.get("current_step") or "")
        next_step = str(next_fields.get("current_step") or metadata.get("progress_step") or current_step or "").strip()
        if "step_started_at" not in metadata:
            metadata["step_started_at"] = row.get("created_at") or now
        if "step_durations" not in metadata:
            metadata["step_durations"] = {}
        if next_step and next_step != str(metadata.get("progress_step") or current_step or ""):
            self._finalize_step_duration(payload=metadata, previous_step=str(metadata.get("progress_step") or current_step or ""), finished_at=now)
            metadata["progress_step"] = next_step
            metadata["step_started_at"] = now
        if str(next_fields.get("status") or row.get("status") or "") in {"failed", "partial", "cancelled", "aborted"}:
            metadata["failure_stage"] = str(next_fields.get("current_step") or row.get("current_step") or next_step or "") or None
        next_fields["metadata"] = metadata
        return next_fields

    def _finalize_step_duration(self, *, payload: dict[str, Any], previous_step: str, finished_at: str) -> None:
        if not previous_step:
            return
        started_at = str(payload.get("step_started_at") or "").strip()
        if not started_at:
            return
        elapsed_seconds = self._elapsed_seconds(started_at, finished_at)
        step_durations = dict(payload.get("step_durations", {}))
        step_durations[previous_step] = round(float(step_durations.get(previous_step) or 0.0) + elapsed_seconds, 3)
        payload["step_durations"] = step_durations

    def _elapsed_seconds(self, started_at: str, finished_at: str) -> float:
        try:
            started = datetime.fromisoformat(started_at)
            finished = datetime.fromisoformat(finished_at)
        except ValueError:
            return 0.0
        return max(0.0, (finished - started).total_seconds())

    def _is_number(self, value: Any) -> bool:
        try:
            float(value)
        except (TypeError, ValueError):
            return False
        return True
