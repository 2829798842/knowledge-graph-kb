"""导入提交、执行与流水线处理的应用服务。"""

from collections.abc import Callable
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any
from uuid import uuid4

from src.config import Settings
from src.knowledge_base.domain import build_paragraph_node_id, utc_now_iso
from src.knowledge_base.importing.excel import (
    SPREADSHEET_SCHEMA_SUFFIX,
    EXCEL_FILE_TYPES,
    SpreadsheetDocumentData,
    build_excel_import_bundle,
    is_spreadsheet_schema_name,
    load_excel_document,
    load_spreadsheet_schema_bytes,
    load_spreadsheet_schema_path,
    supports_excel_file_type,
    workbook_stem_from_sidecar,
)
from src.knowledge_base.importing.payload_normalizers import build_structured_import_item, build_text_import_item
from src.knowledge_base.importing.strategy_router import select_strategy, split_text_by_strategy
from src.knowledge_base.infrastructure import (
    GraphRepository,
    ImportJobRepository,
    OpenAiGateway,
    RecordRepository,
    SourceRepository,
    VectorIndex,
    VectorIndexRecord,
)
from src.knowledge_base.importing.chunking import count_tokens
from src.knowledge_base.importing.parser import (
    SUPPORTED_EXTENSION_DISPLAY,
    UnsupportedFileTypeError,
    detect_file_type,
    extract_text,
)
from src.utils.file_utils import sanitize_filename

from .model_config_service import ModelConfigService

PipelineProgressCallback = Callable[[float, str, str], None]
CancelChecker = Callable[[], bool]

CONTENT_TYPE_EXTENSION_MAP: dict[str, str] = {
    "text/plain": ".txt",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel.sheet.macroenabled.12": ".xlsm",
    "application/vnd.ms-excel": ".xls",
}

SPREADSHEET_FILE_TYPES = EXCEL_FILE_TYPES


class ImportCancelledError(RuntimeError):
    """在当前导入任务被取消时抛出。"""


class ExtractionWindow:
    """表示一个 LLM 抽取窗口。"""

    def __init__(self, index: int, chunk_indexes: list[int], text: str) -> None:
        self.index = index
        self.chunk_indexes = chunk_indexes
        self.text = text


class ImportPipeline:
    """将单个归一化导入项处理为知识库数据。"""

    def __init__(
        self,
        *,
        settings: Settings,
        model_config_service: ModelConfigService,
        job_repository: ImportJobRepository,
        source_repository: SourceRepository,
        graph_repository: GraphRepository,
        record_repository: RecordRepository,
        vector_index: VectorIndex,
        openai_gateway: OpenAiGateway,
    ) -> None:
        self.settings = settings
        self.model_config_service = model_config_service
        self.job_repository = job_repository
        self.source_repository = source_repository
        self.graph_repository = graph_repository
        self.record_repository = record_repository
        self.vector_index = vector_index
        self.openai_gateway = openai_gateway

    def process_item(
        self,
        *,
        job_id: str,
        file_id: str,
        item: dict[str, Any],
        on_progress: PipelineProgressCallback,
        is_cancel_requested: CancelChecker,
    ) -> str:
        """处理单个导入项并写入来源、段落、向量与图数据。"""

        self._ensure_not_cancelled(is_cancel_requested)
        source_name = str(item["name"])
        file_type = str(item.get("file_type") or "").strip().lower().lstrip(".")
        spreadsheet_document = self._resolve_spreadsheet_document(item=item, file_type=file_type)
        raw_text = self._resolve_text(item=item, spreadsheet_document=spreadsheet_document)
        if not raw_text.strip() and not item.get("structured_paragraphs"):
            raise ValueError("No extractable text found for this import item.")

        strategy = select_strategy(
            requested_strategy=str(item.get("strategy") or "auto"),
            text=raw_text,
            file_name=source_name,
        )
        spreadsheet_bundle: dict[str, Any] | None = None
        sheet_names: list[str] = []
        if spreadsheet_document is not None:
            spreadsheet_bundle = build_excel_import_bundle(
                document=spreadsheet_document,
                strategy=strategy,
                source_file_type=file_type,
                source_name=source_name,
                schema_payload=item.get("spreadsheet_schema"),
            )
            sheet_names = [str(name) for name in spreadsheet_bundle.get("worksheet_names", [])]

        import_file_metadata: dict[str, Any] = {
            **dict(item.get("metadata", {})),
            "retry_payload": item,
            "detected_strategy": strategy,
            "source_file_type": file_type,
        }
        if spreadsheet_bundle is not None:
            import_file_metadata.update(dict(spreadsheet_bundle.get("metadata", {})))
        if sheet_names:
            import_file_metadata["spreadsheet_sheets"] = sheet_names

        self.job_repository.update_job_file(
            file_id,
            strategy=strategy,
            status="running",
            current_step="splitting",
            progress=8.0,
            metadata=import_file_metadata,
        )
        on_progress(8.0, "splitting", f"Splitting text with strategy: {strategy} ({source_name})")

        paragraph_payloads = self._build_paragraph_payloads(
            raw_text=raw_text,
            item=item,
            strategy=strategy,
            source_file_type=file_type,
            spreadsheet_bundle=spreadsheet_bundle,
        )
        chunk_rows = self.job_repository.create_job_chunks(
            job_id=job_id,
            file_id=file_id,
            chunk_previews=[str(paragraph["content"]) for paragraph in paragraph_payloads],
        )
        self._ensure_not_cancelled(is_cancel_requested)

        source = self.source_repository.create_source(
            name=source_name,
            source_kind=str(item["source_kind"]),
            input_mode=str(item["input_mode"]),
            file_type=file_type,
            storage_path=item.get("storage_path"),
            strategy=strategy,
            status="running",
            summary=None,
            metadata={
                **dict(item.get("metadata", {})),
                "job_id": job_id,
                "file_id": file_id,
                "detected_strategy": strategy,
                "source_file_type": file_type,
                **(dict(spreadsheet_bundle.get("metadata", {})) if spreadsheet_bundle is not None else {}),
                **({"spreadsheet_sheets": sheet_names} if sheet_names else {}),
            },
        )
        self.job_repository.update_job_file(file_id, source_id=str(source["id"]), current_step="indexing", progress=18.0)
        on_progress(18.0, "indexing", f"Indexing source: {source_name}")

        paragraph_rows = self.source_repository.add_paragraphs(source_id=str(source["id"]), paragraphs=paragraph_payloads)
        self.record_repository.sync_rows_for_paragraphs(paragraph_rows)
        self._ensure_not_cancelled(is_cancel_requested)

        self.job_repository.update_job_file(file_id, current_step="embedding", progress=36.0)
        on_progress(36.0, "embedding", f"Embedding {len(paragraph_rows)} paragraph(s)")
        embeddings = self.openai_gateway.embed_texts([str(paragraph["content"]) for paragraph in paragraph_rows])
        vector_records = [
            VectorIndexRecord(
                paragraph_id=str(paragraph["id"]),
                source_id=str(source["id"]),
                node_id=build_paragraph_node_id(str(paragraph["id"])),
                text=str(paragraph["content"]),
                knowledge_type=str(paragraph["knowledge_type"]),
            )
            for paragraph in paragraph_rows
        ]
        for paragraph in paragraph_rows:
            self.source_repository.update_paragraph(str(paragraph["id"]), vector_state="ready")
        self.vector_index.add_embeddings(
            model_signature=self.model_config_service.embedding_model_signature(),
            records=vector_records,
            embeddings=embeddings,
        )
        self._ensure_not_cancelled(is_cancel_requested)

        extraction_result: dict[str, Any]
        if spreadsheet_bundle is not None:
            extraction_result = {
                "entities": list(spreadsheet_bundle.get("entities", [])),
                "relations": list(spreadsheet_bundle.get("relations", [])),
            }
        elif item.get("structured_entities") or item.get("structured_relations"):
            extraction_result = {
                "entities": list(item.get("structured_entities", [])),
                "relations": list(item.get("structured_relations", [])),
            }
        else:
            extraction_result = self._extract_document_graph(
                document_name=source_name,
                paragraph_rows=paragraph_rows,
                file_id=file_id,
                on_progress=on_progress,
                is_cancel_requested=is_cancel_requested,
            )
        self._ensure_not_cancelled(is_cancel_requested)

        self.job_repository.update_job_file(file_id, current_step="writing", progress=84.0)
        on_progress(84.0, "writing", f"Writing graph data for: {source_name}")
        self._write_entities_and_relations(
            source_id=str(source["id"]),
            paragraph_rows=paragraph_rows,
            extraction_result=extraction_result,
        )
        for chunk_row, paragraph_row in zip(chunk_rows, paragraph_rows, strict=True):
            self.job_repository.update_job_chunk(
                str(chunk_row["id"]),
                paragraph_id=str(paragraph_row["id"]),
                status="completed",
                step="completed",
                progress=100.0,
            )

        summary = (
            f"{len(paragraph_rows)} paragraphs, "
            f"{len(extraction_result['entities'])} entities, "
            f"{len(extraction_result['relations'])} relations"
        )
        self.source_repository.update_source(
            str(source["id"]),
            status="ready",
            summary=summary,
            metadata={**dict(source["metadata"]), "paragraph_count": len(paragraph_rows)},
        )
        self.job_repository.update_job_file(
            file_id,
            status="completed",
            current_step="completed",
            progress=100.0,
        )
        on_progress(100.0, "completed", f"Completed import: {source_name}")
        return str(source["id"])

    def _resolve_text(
        self,
        *,
        item: dict[str, Any],
        spreadsheet_document: SpreadsheetDocumentData | None = None,
    ) -> str:
        text = str(item.get("text") or "").strip()
        if text:
            return text
        if spreadsheet_document is not None:
            return spreadsheet_document.to_text()
        storage_path = str(item.get("storage_path") or "").strip()
        if storage_path:
            return extract_text(Path(storage_path))
        return ""

    def _resolve_spreadsheet_document(
        self,
        *,
        item: dict[str, Any],
        file_type: str,
    ) -> SpreadsheetDocumentData | None:
        if not supports_excel_file_type(file_type):
            return None
        storage_path = str(item.get("storage_path") or "").strip()
        if not storage_path:
            return None
        return load_excel_document(Path(storage_path), file_type=file_type)

    def _build_paragraph_payloads(
        self,
        *,
        raw_text: str,
        item: dict[str, Any],
        strategy: str,
        source_file_type: str,
        spreadsheet_bundle: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        structured_paragraphs = list(item.get("structured_paragraphs") or [])
        if structured_paragraphs:
            return [
                {
                    "position": index,
                    "content": str(paragraph.get("content") or "").strip(),
                    "knowledge_type": str(paragraph.get("knowledge_type") or "mixed"),
                    "token_count": count_tokens(str(paragraph.get("content") or "")),
                    "vector_state": "pending",
                    "metadata": dict(paragraph.get("metadata", {})),
                }
                for index, paragraph in enumerate(structured_paragraphs)
                if str(paragraph.get("content") or "").strip()
            ]
        if spreadsheet_bundle is not None:
            return [
                {
                    "position": index,
                    "content": str(paragraph.get("content") or "").strip(),
                    "knowledge_type": str(paragraph.get("knowledge_type") or strategy or "factual"),
                    "token_count": int(paragraph.get("token_count") or count_tokens(str(paragraph.get("content") or ""))),
                    "vector_state": str(paragraph.get("vector_state") or "pending"),
                    "metadata": dict(paragraph.get("metadata", {})),
                }
                for index, paragraph in enumerate(list(spreadsheet_bundle.get("paragraphs") or []))
                if str(paragraph.get("content") or "").strip()
            ]
        paragraphs = split_text_by_strategy(text=raw_text, strategy=strategy, settings=self.settings)
        return [
            {
                "position": index,
                "content": paragraph,
                "knowledge_type": strategy if strategy != "auto" else "mixed",
                "token_count": count_tokens(paragraph),
                "vector_state": "pending",
                "metadata": {
                    "strategy": strategy,
                    "source_file_type": source_file_type,
                    "is_spreadsheet": source_file_type in SPREADSHEET_FILE_TYPES,
                },
            }
            for index, paragraph in enumerate(paragraphs)
            if paragraph.strip()
        ]

    def _extract_document_graph(
        self,
        *,
        document_name: str,
        paragraph_rows: list[dict[str, Any]],
        file_id: str,
        on_progress: PipelineProgressCallback,
        is_cancel_requested: CancelChecker,
    ) -> dict[str, Any]:
        windows = _build_extraction_windows([str(paragraph["content"]) for paragraph in paragraph_rows])
        partial_results: list[dict[str, Any]] = []
        for window_index, window in enumerate(windows, start=1):
            self._ensure_not_cancelled(is_cancel_requested)
            total_windows = len(windows)
            progress_ratio = max(0.0, min((window_index - 1) / max(total_windows, 1), 1.0))
            file_progress = round(52.0 + 30.0 * progress_ratio, 2)
            self.job_repository.update_job_file(file_id, current_step="extracting", progress=file_progress)
            on_progress(file_progress, "extracting", f"{document_name} extracting chunks: {window_index}/{total_windows}")
            partial_results.append(
                self.openai_gateway.extract_entities(
                    document_name=document_name,
                    text=window.text,
                    window_label=f"window-{window.index}",
                )
            )
        return _merge_extraction_results(partial_results)

    def _write_entities_and_relations(
        self,
        *,
        source_id: str,
        paragraph_rows: list[dict[str, Any]],
        extraction_result: dict[str, Any],
    ) -> None:
        entity_rows: dict[str, dict[str, Any]] = {}
        paragraph_text_map = {str(paragraph["id"]): str(paragraph["content"]) for paragraph in paragraph_rows}
        for entity in extraction_result["entities"]:
            row = self.graph_repository.upsert_entity(
                display_name=str(entity["name"]),
                description=str(entity.get("description") or ""),
                metadata={**dict(entity.get("metadata", {})), "source_id": source_id},
            )
            entity_rows[str(entity["name"]).strip().lower()] = row
            for paragraph in paragraph_rows:
                mention_count = self._match_count(str(entity["name"]), str(paragraph["content"]))
                if mention_count <= 0:
                    continue
                self.graph_repository.link_paragraph_entity(
                    paragraph_id=str(paragraph["id"]),
                    entity_id=str(row["id"]),
                    mention_count=mention_count,
                    metadata={"source_id": source_id},
                )
        for relation in extraction_result["relations"]:
            subject_row = entity_rows.get(str(relation["subject"]).strip().lower())
            object_row = entity_rows.get(str(relation["object"]).strip().lower())
            if subject_row is None or object_row is None:
                continue
            source_paragraph_id = self._resolve_relation_source_paragraph(
                paragraph_rows=paragraph_rows,
                subject=str(relation["subject"]),
                object_name=str(relation["object"]),
                paragraph_text_map=paragraph_text_map,
            )
            relation_row = self.graph_repository.create_relation(
                subject_entity_id=str(subject_row["id"]),
                predicate=str(relation["predicate"]),
                object_entity_id=str(object_row["id"]),
                confidence=float(relation.get("confidence") or 1.0),
                source_paragraph_id=source_paragraph_id,
                metadata={**dict(relation.get("metadata", {})), "source_id": source_id},
            )
            if source_paragraph_id:
                self.graph_repository.link_paragraph_relation(
                    paragraph_id=source_paragraph_id,
                    relation_id=str(relation_row["id"]),
                    metadata={**dict(relation.get("metadata", {})), "source_id": source_id},
                )

    def _resolve_relation_source_paragraph(
        self,
        *,
        paragraph_rows: list[dict[str, Any]],
        subject: str,
        object_name: str,
        paragraph_text_map: dict[str, str],
    ) -> str | None:
        subject_lower = subject.strip().lower()
        object_lower = object_name.strip().lower()
        for paragraph in paragraph_rows:
            paragraph_id = str(paragraph["id"])
            content = paragraph_text_map[paragraph_id].lower()
            if subject_lower in content and object_lower in content:
                return paragraph_id
        for paragraph in paragraph_rows:
            paragraph_id = str(paragraph["id"])
            content = paragraph_text_map[paragraph_id].lower()
            if subject_lower in content or object_lower in content:
                return paragraph_id
        return None

    def _match_count(self, entity_name: str, content: str) -> int:
        normalized_name = entity_name.strip().lower()
        if not normalized_name:
            return 0
        return max(content.lower().count(normalized_name), 0)

    def _ensure_not_cancelled(self, is_cancel_requested: CancelChecker) -> None:
        if is_cancel_requested():
            raise ImportCancelledError("Import job has been cancelled.")


class ImportExecutor:
    """在进程内使用线程执行导入任务。"""

    def __init__(self, *, job_repository: ImportJobRepository, pipeline: ImportPipeline) -> None:
        self.job_repository = job_repository
        self.pipeline = pipeline
        self._threads: dict[str, Thread] = {}
        self._cancellations: dict[str, Event] = {}
        self._lock = Lock()

    def submit(self, *, job_id: str, items: list[dict[str, Any]]) -> None:
        """提交导入任务到后台线程执行。"""

        cancellation_event = Event()
        thread = Thread(
            target=self._run_job,
            kwargs={"job_id": job_id, "items": items, "cancellation_event": cancellation_event},
            daemon=True,
        )
        with self._lock:
            self._threads[job_id] = thread
            self._cancellations[job_id] = cancellation_event
        thread.start()

    def cancel(self, job_id: str) -> None:
        """标记指定导入任务为取消状态。"""

        with self._lock:
            cancellation_event = self._cancellations.get(job_id)
        if cancellation_event is not None:
            cancellation_event.set()

    def _run_job(self, *, job_id: str, items: list[dict[str, Any]], cancellation_event: Event) -> None:
        file_rows = self.job_repository.list_job_files(job_id)
        had_success = False
        try:
            self.job_repository.update_job(
                job_id,
                status="running",
                current_step="preparing",
                started_at=utc_now_iso(),
                message="Starting import job",
            )
            for file_index, (file_row, item) in enumerate(zip(file_rows, items, strict=True)):
                file_id = str(file_row["id"])
                try:
                    self.pipeline.process_item(
                        job_id=job_id,
                        file_id=file_id,
                        item=item,
                        on_progress=lambda progress, step, message, index=file_index: self._update_job_progress(
                            job_id=job_id,
                            file_index=index,
                            total_files=len(file_rows),
                            file_progress=progress,
                            current_step=step,
                            message=message,
                        ),
                        is_cancel_requested=cancellation_event.is_set,
                    )
                    had_success = True
                except ImportCancelledError as exc:
                    self._mark_file_cancelled(file_id=file_id, job_id=job_id, error_message=str(exc))
                    self.job_repository.update_job(
                        job_id,
                        status="cancelled",
                        current_step="cancelled",
                        finished_at=utc_now_iso(),
                        message="Import cancelled",
                        error=str(exc),
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    self.job_repository.update_job_file(
                        file_id,
                        status="failed",
                        current_step="failed",
                        error=str(exc),
                    )
                    for chunk_row in self.job_repository.list_job_chunks(job_id, file_id):
                        self.job_repository.update_job_chunk(
                            str(chunk_row["id"]),
                            status="failed",
                            step="failed",
                            error=str(exc),
                        )
            latest_job = self.job_repository.refresh_job_counters(job_id) or self.job_repository.get_job(job_id)
            failed_files = int(latest_job.get("failed_files", 0)) if latest_job else 0
            final_status = "completed"
            if failed_files > 0:
                final_status = "partial" if had_success else "failed"
            self.job_repository.update_job(
                job_id,
                status=final_status,
                current_step="completed",
                progress=100.0,
                finished_at=utc_now_iso(),
                message="Import completed" if failed_files == 0 else "Import completed with failed files",
                error=None if failed_files == 0 else latest_job.get("error"),
            )
        finally:
            if not had_success and cancellation_event.is_set():
                self.job_repository.update_job(job_id, status="cancelled", current_step="cancelled", finished_at=utc_now_iso())
            with self._lock:
                self._threads.pop(job_id, None)
                self._cancellations.pop(job_id, None)

    def _update_job_progress(
        self,
        *,
        job_id: str,
        file_index: int,
        total_files: int,
        file_progress: float,
        current_step: str,
        message: str,
    ) -> None:
        overall_progress = round(((file_index + file_progress / 100.0) / max(total_files, 1)) * 100.0, 2)
        self.job_repository.update_job(
            job_id,
            status="running",
            current_step=current_step,
            progress=overall_progress,
            message=message,
        )

    def _mark_file_cancelled(self, *, file_id: str, job_id: str, error_message: str) -> None:
        self.job_repository.update_job_file(
            file_id,
            status="cancelled",
            current_step="cancelled",
            error=error_message,
        )
        for chunk_row in self.job_repository.list_job_chunks(job_id, file_id):
            self.job_repository.update_job_chunk(
                str(chunk_row["id"]),
                status="cancelled",
                step="cancelled",
                error=error_message,
            )


class ImportService:
    """导入任务的提交与编排入口。"""

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: ImportJobRepository,
        executor: ImportExecutor,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.executor = executor

    def submit_uploads(self, *, files: list[tuple[str, bytes, str | None]], strategy: str) -> dict[str, Any]:
        """提交上传文件导入任务。"""

        if not files:
            raise ValueError("Please upload at least one file.")
        upload_root = self.settings.resolved_kb_upload_dir / "uploads"
        upload_root.mkdir(parents=True, exist_ok=True)
        normalized_files = [
            self._normalize_upload_file(
                original_name=original_name,
                content_type=content_type,
                contents=contents,
            )
            for original_name, contents, content_type in files
        ]
        schema_by_stem = self._collect_upload_sidecars(normalized_files)
        data_files = [item for item in normalized_files if not bool(item.get("is_sidecar_schema"))]
        if not data_files:
            raise ValueError("No importable workbook or document files were uploaded.")
        items: list[dict[str, Any]] = []
        for normalized_file in data_files:
            safe_name = sanitize_filename(str(normalized_file["storage_name"])) or f"upload.{normalized_file['file_type']}"
            destination = upload_root / f"{uuid4()}__{safe_name}"
            destination.write_bytes(bytes(normalized_file["contents"]))
            item = build_text_import_item(
                name=str(normalized_file["display_name"]),
                text="",
                source_kind="upload",
                input_mode="file",
                strategy=strategy,
                file_type=str(normalized_file["file_type"]),
                storage_path=str(destination),
                metadata={
                    "content_type": str(normalized_file["content_type"]),
                    "size_bytes": int(normalized_file["size_bytes"]),
                },
            )
            self._attach_upload_sidecar_schema(
                item=item,
                normalized_file=normalized_file,
                schema_by_stem=schema_by_stem,
            )
            items.append(item)
        return self._create_job(source="upload", input_mode="file", strategy=strategy, items=items)

    def submit_paste(
        self,
        *,
        title: str,
        content: str,
        strategy: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """提交粘贴文本导入任务。"""

        normalized_title = str(title or "").strip() or "Pasted content"
        normalized_content = str(content or "").strip()
        if not normalized_content:
            raise ValueError("Pasted content cannot be empty.")
        item = build_text_import_item(
            name=normalized_title,
            text=normalized_content,
            source_kind="paste",
            input_mode="text",
            strategy=strategy,
            metadata=dict(metadata or {}),
        )
        return self._create_job(source="paste", input_mode="text", strategy=strategy, items=[item])

    def submit_scan(self, *, root_path: str, glob_pattern: str, strategy: str) -> dict[str, Any]:
        """扫描目录并批量提交文件导入任务。"""

        root = Path(root_path).resolve()
        allowed_roots = [path for path in self.settings.resolved_kb_scan_roots if path.exists()]
        if allowed_roots and not any(root.is_relative_to(allowed_root) for allowed_root in allowed_roots):
            raise ValueError("Scan path is not under an allowed root.")
        if not root.exists() or not root.is_dir():
            raise ValueError("Scan path must be an existing directory.")
        normalized_pattern = str(glob_pattern or "**/*").strip() or "**/*"
        items: list[dict[str, Any]] = []
        skipped_unsupported_count = 0
        for file_path in sorted(root.glob(normalized_pattern)):
            if not file_path.is_file():
                continue
            try:
                file_type = detect_file_type(file_path)
            except UnsupportedFileTypeError:
                skipped_unsupported_count += 1
                continue
            item = build_text_import_item(
                name=file_path.name,
                text="",
                source_kind="scan",
                input_mode="file",
                strategy=strategy,
                file_type=file_type,
                storage_path=str(file_path),
                metadata={
                    "root_path": str(root),
                    "glob_pattern": normalized_pattern,
                    "skipped_unsupported_count": skipped_unsupported_count,
                },
            )
            self._attach_scan_sidecar_schema(item=item, file_path=file_path, file_type=file_type)
            items.append(item)
        if not items:
            if skipped_unsupported_count > 0:
                raise ValueError(f"No supported files found. Supported types: {SUPPORTED_EXTENSION_DISPLAY}")
            raise ValueError("Scan path does not contain files matching the pattern.")
        return self._create_job(source="scan", input_mode="file", strategy=strategy, items=items)

    def submit_openie(
        self,
        *,
        title: str,
        payload: dict[str, Any],
        strategy: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """提交 OpenIE 结构化导入任务。"""

        item = build_structured_import_item(
            name=str(title or "").strip() or "OpenIE import",
            payload=payload,
            source_kind="openie",
            input_mode="json",
            strategy=strategy,
            metadata=dict(metadata or {}),
        )
        return self._create_job(source="openie", input_mode="json", strategy=strategy, items=[item])

    def submit_convert(
        self,
        *,
        title: str,
        payload: dict[str, Any],
        strategy: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """提交转换后的结构化导入任务。"""

        item = build_structured_import_item(
            name=str(title or "").strip() or "Converted import",
            payload=payload,
            source_kind="convert",
            input_mode="json",
            strategy=strategy,
            metadata=dict(metadata or {}),
        )
        return self._create_job(source="convert", input_mode="json", strategy=strategy, items=[item])

    def list_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """按时间倒序返回导入任务列表。"""

        return [self.job_repository.hydrate_job(job) for job in self.job_repository.list_jobs(limit=limit)]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """读取单个导入任务详情。"""

        job = self.job_repository.get_job(job_id)
        if job is None:
            return None
        return self.job_repository.hydrate_job(job)

    def list_job_chunks(self, job_id: str, file_id: str) -> list[dict[str, Any]]:
        """列出某个导入文件对应的分块处理记录。"""

        if self.job_repository.get_job(job_id) is None:
            return []
        return self.job_repository.list_job_chunks(job_id, file_id)

    def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        """取消指定导入任务并返回最新状态。"""

        job = self.job_repository.get_job(job_id)
        if job is None:
            return None
        self.executor.cancel(job_id)
        updated_job = self.job_repository.update_job(
            job_id,
            status="cancelled",
            current_step="cancelled",
            finished_at=utc_now_iso(),
            message="Import cancelled.",
        )
        return self.job_repository.hydrate_job(updated_job) if updated_job is not None else None

    def retry_failed(self, job_id: str) -> dict[str, Any]:
        """重试指定任务中失败的导入文件。"""

        job = self.get_job(job_id)
        if job is None:
            raise ValueError("Import job not found.")
        failed_items: list[dict[str, Any]] = []
        for file_row in list(job.get("files") or []):
            if str(file_row.get("status") or "") != "failed":
                continue
            retry_payload = dict(file_row.get("metadata", {})).get("retry_payload")
            if isinstance(retry_payload, dict):
                failed_items.append(retry_payload)
        if not failed_items:
            raise ValueError("Import job has no failed files to retry.")
        return self._create_job(
            source=f"retry:{job['source']}",
            input_mode=str(job["input_mode"]),
            strategy=str(job["strategy"]),
            items=failed_items,
        )

    def _create_job(
        self,
        *,
        source: str,
        input_mode: str,
        strategy: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not items:
            raise ValueError("No import items were produced.")
        job = self.job_repository.create_job(
            source=source,
            input_mode=input_mode,
            strategy=strategy,
            params={"source": source, "input_mode": input_mode, "strategy": strategy},
            total_files=len(items),
        )
        for item in items:
            self.job_repository.create_job_file(
                job_id=str(job["id"]),
                name=str(item["name"]),
                source_kind=str(item["source_kind"]),
                input_mode=str(item["input_mode"]),
                strategy=strategy,
                storage_path=item.get("storage_path"),
                metadata={**dict(item.get("metadata", {})), "retry_payload": item},
            )
        self.executor.submit(job_id=str(job["id"]), items=items)
        return self.get_job(str(job["id"])) or job

    def _normalize_upload_file(
        self,
        *,
        original_name: str,
        content_type: str | None,
        contents: bytes,
    ) -> dict[str, Any]:
        normalized_name = str(original_name or "").strip()
        normalized_content_type = str(content_type or "").split(";", maxsplit=1)[0].strip().lower()
        if is_spreadsheet_schema_name(normalized_name):
            return {
                "display_name": normalized_name or "spreadsheet.schema.json",
                "storage_name": normalized_name or "spreadsheet.schema.json",
                "file_type": "schema_json",
                "content_type": normalized_content_type or "application/json",
                "size_bytes": len(contents),
                "contents": contents,
                "is_sidecar_schema": True,
                "workbook_stem": workbook_stem_from_sidecar(normalized_name),
            }

        candidate_paths: list[Path] = []
        if normalized_name:
            candidate_paths.append(Path(normalized_name))
        fallback_extension = CONTENT_TYPE_EXTENSION_MAP.get(normalized_content_type)
        if fallback_extension:
            candidate_paths.append(Path(f"upload{fallback_extension}"))

        for candidate_path in candidate_paths:
            try:
                file_type = detect_file_type(candidate_path)
            except UnsupportedFileTypeError:
                continue
            display_name = normalized_name or candidate_path.name
            storage_name = normalized_name or candidate_path.name
            return {
                "display_name": display_name,
                "storage_name": storage_name,
                "file_type": file_type,
                "content_type": normalized_content_type,
                "size_bytes": len(contents),
                "contents": contents,
                "is_sidecar_schema": False,
            }

        display_name = normalized_name or "upload"
        raise ValueError(f"{display_name} is not supported. Supported file types: {SUPPORTED_EXTENSION_DISPLAY}")

    def _collect_upload_sidecars(self, normalized_files: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        schema_by_stem: dict[str, dict[str, Any]] = {}
        for normalized_file in normalized_files:
            if not bool(normalized_file.get("is_sidecar_schema")):
                continue
            workbook_stem = str(normalized_file.get("workbook_stem") or "").strip().casefold()
            if not workbook_stem:
                continue
            schema_by_stem[workbook_stem] = {
                "file_name": str(normalized_file["display_name"]),
                "payload": load_spreadsheet_schema_bytes(
                    bytes(normalized_file["contents"]),
                    file_name=str(normalized_file["display_name"]),
                ),
            }
        return schema_by_stem

    def _attach_upload_sidecar_schema(
        self,
        *,
        item: dict[str, Any],
        normalized_file: dict[str, Any],
        schema_by_stem: dict[str, dict[str, Any]],
    ) -> None:
        file_type = str(normalized_file.get("file_type") or "")
        if file_type not in SPREADSHEET_FILE_TYPES:
            return
        workbook_stem = Path(str(normalized_file["storage_name"])).stem.casefold()
        schema_entry = schema_by_stem.get(workbook_stem)
        if schema_entry is None:
            return
        item["spreadsheet_schema"] = dict(schema_entry["payload"])
        item["metadata"] = {
            **dict(item.get("metadata", {})),
            "spreadsheet_schema_name": str(schema_entry["file_name"]),
            "spreadsheet_schema_present": True,
        }

    def _attach_scan_sidecar_schema(self, *, item: dict[str, Any], file_path: Path, file_type: str) -> None:
        if file_type not in SPREADSHEET_FILE_TYPES:
            return
        sidecar_path = file_path.with_name(f"{file_path.stem}{SPREADSHEET_SCHEMA_SUFFIX}")
        if not sidecar_path.is_file():
            return
        item["spreadsheet_schema"] = load_spreadsheet_schema_path(sidecar_path)
        item["metadata"] = {
            **dict(item.get("metadata", {})),
            "spreadsheet_schema_name": sidecar_path.name,
            "spreadsheet_schema_present": True,
        }


def _build_extraction_windows(paragraph_texts: list[str], *, max_tokens: int = 1800) -> list[ExtractionWindow]:
    windows: list[ExtractionWindow] = []
    current_indexes: list[int] = []
    current_parts: list[str] = []
    current_token_count = 0
    for index, paragraph_text in enumerate(paragraph_texts):
        text = str(paragraph_text).strip()
        if not text:
            continue
        paragraph_tokens = count_tokens(text)
        if current_parts and current_token_count + paragraph_tokens > max_tokens:
            windows.append(
                ExtractionWindow(
                    index=len(windows),
                    chunk_indexes=current_indexes.copy(),
                    text="\n\n".join(current_parts),
                )
            )
            current_indexes = []
            current_parts = []
            current_token_count = 0
        current_indexes.append(index)
        current_parts.append(text)
        current_token_count += paragraph_tokens
    if current_parts:
        windows.append(
            ExtractionWindow(
                index=len(windows),
                chunk_indexes=current_indexes.copy(),
                text="\n\n".join(current_parts),
            )
        )
    return windows or [ExtractionWindow(index=0, chunk_indexes=[], text="")]


def _merge_extraction_results(partial_results: list[dict[str, Any]]) -> dict[str, Any]:
    entity_map: dict[str, dict[str, Any]] = {}
    relation_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for partial_result in partial_results:
        for entity in list(partial_result.get("entities") or []):
            entity_name = str(entity.get("name") or "").strip()
            if not entity_name:
                continue
            entity_key = entity_name.casefold()
            existing = entity_map.get(entity_key)
            if existing is None:
                entity_map[entity_key] = {
                    "name": entity_name,
                    "description": str(entity.get("description") or "").strip(),
                    "metadata": dict(entity.get("metadata", {})),
                }
                continue
            existing_description = str(existing.get("description") or "")
            next_description = str(entity.get("description") or "").strip()
            if len(next_description) > len(existing_description):
                existing["description"] = next_description
            existing["metadata"] = {**dict(existing.get("metadata", {})), **dict(entity.get("metadata", {}))}
        for relation in list(partial_result.get("relations") or []):
            subject = str(relation.get("subject") or relation.get("source") or "").strip()
            predicate = str(relation.get("predicate") or relation.get("relation") or "").strip()
            object_name = str(relation.get("object") or relation.get("target") or "").strip()
            if not subject or not predicate or not object_name:
                continue
            relation_key = (subject.casefold(), predicate.casefold(), object_name.casefold())
            confidence = float(relation.get("confidence") or relation.get("weight") or 1.0)
            existing_relation = relation_map.get(relation_key)
            if existing_relation is None or confidence > float(existing_relation.get("confidence") or 0.0):
                relation_map[relation_key] = {
                    "subject": subject,
                    "predicate": predicate,
                    "object": object_name,
                    "confidence": confidence,
                    "metadata": dict(relation.get("metadata", {})),
                }
            elif existing_relation is not None:
                existing_relation["metadata"] = {
                    **dict(existing_relation.get("metadata", {})),
                    **dict(relation.get("metadata", {})),
                }
    return {
        "entities": list(entity_map.values()),
        "relations": list(relation_map.values()),
    }
