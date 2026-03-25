"""知识导入任务的提交、执行与处理流水线。"""

from collections.abc import Callable
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any
from uuid import uuid4

from src.config import Settings
from src.kb.common import build_paragraph_node_id, utc_now_iso
from src.kb.importing.excel import (
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
from src.kb.importing.payloads import build_structured_import_item, build_text_import_item
from src.kb.importing.strategy import select_strategy, split_text_by_strategy
from src.kb.providers import OpenAiGateway
from src.kb.storage import (
    GraphStore,
    ImportJobStore,
    RecordStore,
    SourceStore,
    VectorIndex,
    VectorIndexRecord,
)
from src.kb.importing.chunking import count_tokens
from src.kb.importing.parser import (
    SUPPORTED_EXTENSION_DISPLAY,
    UnsupportedFileTypeError,
    detect_file_type,
    extract_text,
)
from src.utils.file import sanitize_filename
from src.utils.logger import get_logger

from ..services.model import ModelConfigService

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

logger = get_logger(__name__)


class ImportCancelledError(RuntimeError):
    """导入任务被取消时抛出。"""


class ExtractionWindow:
    """LLM 抽取窗口。

    Attributes:
        index (int): 窗口索引。
        chunk_indexes (list[int]): 当前窗口包含的段落下标。
        text (str): 当前窗口拼接文本。
    """

    def __init__(self, index: int, chunk_indexes: list[int], text: str) -> None:
        """初始化抽取窗口。

        Args:
            index: 窗口索引。
            chunk_indexes: 段落下标列表。
            text: 窗口文本。
        """

        self.index = index
        self.chunk_indexes = chunk_indexes
        self.text = text


class ImportPipeline:
    """单文件导入处理流水线。

    Attributes:
        settings (Settings): 全局配置对象。
        model_config_service (ModelConfigService): 模型配置服务。
        job_store (ImportJobStore): 导入任务仓储。
        source_store (SourceStore): 来源仓储。
        graph_store (GraphStore): 图谱仓储。
        record_store (RecordStore): 结构化记录仓储。
        vector_index (VectorIndex): 向量索引服务。
        openai_gateway (OpenAiGateway): 模型网关。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        model_config_service: ModelConfigService,
        job_store: ImportJobStore,
        source_store: SourceStore,
        graph_store: GraphStore,
        record_store: RecordStore,
        vector_index: VectorIndex,
        openai_gateway: OpenAiGateway,
    ) -> None:
        """初始化导入流水线。

        Args:
            settings: 全局配置对象。
            model_config_service: 模型配置服务。
            job_store: 任务仓储。
            source_store: 来源仓储。
            graph_store: 图谱仓储。
            record_store: 结构化记录仓储。
            vector_index: 向量索引服务。
            openai_gateway: 模型网关。
        """

        self.settings = settings
        self.model_config_service = model_config_service
        self.job_store = job_store
        self.source_store = source_store
        self.graph_store = graph_store
        self.record_store = record_store
        self.vector = vector_index
        self.gateway = openai_gateway

    def process_item(
        self,
        *,
        job_id: str,
        file_id: str,
        item: dict[str, Any],
        on_progress: PipelineProgressCallback,
        is_cancel_requested: CancelChecker,
    ) -> str:
        """处理单个导入项并写入来源、段落、向量与图谱。

        Args:
            job_id: 导入任务 ID。
            file_id: 导入文件 ID。
            item: 归一化导入项。
            on_progress: 进度回调。
            is_cancel_requested: 取消检查函数。

        Returns:
            str: 创建后的来源 ID。

        Raises:
            ValueError: 当导入内容为空或无可处理内容时抛出。
            ImportCancelledError: 当导入流程被取消时抛出。
        """

        self._ensure_not_cancelled(is_cancel_requested)
        source_name = str(item["name"])
        file_type = str(item.get("file_type") or "").strip().lower().lstrip(".")
        logger.info(
            "开始处理导入文件：job_id=%s file_id=%s source_name=%s file_type=%s source_kind=%s input_mode=%s",
            job_id,
            file_id,
            source_name,
            file_type or "none",
            str(item.get("source_kind") or ""),
            str(item.get("input_mode") or ""),
        )
        spreadsheet_document = self._resolve_spreadsheet_document(item=item, file_type=file_type)
        raw_text = self._resolve_text(item=item, spreadsheet_document=spreadsheet_document)
        logger.debug(
            "导入文件解析完成：job_id=%s file_id=%s source_name=%s raw_text_length=%s has_spreadsheet_document=%s",
            job_id,
            file_id,
            source_name,
            len(raw_text),
            spreadsheet_document is not None,
        )
        if not raw_text.strip() and not item.get("structured_paragraphs"):
            logger.warning(
                "导入文件没有可提取文本：job_id=%s file_id=%s source_name=%s",
                job_id,
                file_id,
                source_name,
            )
            raise ValueError("当前导入项没有可提取的文本内容。")

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
            logger.info(
                "已生成结构化表格导入包：job_id=%s file_id=%s source_name=%s worksheet_count=%s "
                "paragraph_count=%s entity_count=%s relation_count=%s",
                job_id,
                file_id,
                source_name,
                len(sheet_names),
                len(list(spreadsheet_bundle.get("paragraphs") or [])),
                len(list(spreadsheet_bundle.get("entities") or [])),
                len(list(spreadsheet_bundle.get("relations") or [])),
            )

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

        self.job_store.update_job_file(
            file_id,
            strategy=strategy,
            status="running",
            current_step="splitting",
            progress=8.0,
            metadata=import_file_metadata,
        )
        on_progress(8.0, "splitting", f"正在按 {strategy} 策略切分文本：{source_name}")

        paragraph_payloads = self._build_paragraph_payloads(
            raw_text=raw_text,
            item=item,
            strategy=strategy,
            source_file_type=file_type,
            spreadsheet_bundle=spreadsheet_bundle,
        )
        logger.info(
            "已生成段落载荷：job_id=%s file_id=%s source_name=%s paragraph_count=%s strategy=%s",
            job_id,
            file_id,
            source_name,
            len(paragraph_payloads),
            strategy,
        )
        logger.debug(
            "段落载荷明细：job_id=%s file_id=%s source_name=%s positions=%s knowledge_types=%s",
            job_id,
            file_id,
            source_name,
            [int(paragraph.get("position") or 0) for paragraph in paragraph_payloads[:12]],
            [str(paragraph.get("knowledge_type") or "") for paragraph in paragraph_payloads[:12]],
        )
        chunk_rows = self.job_store.create_job_chunks(
            job_id=job_id,
            file_id=file_id,
            chunk_previews=[str(paragraph["content"]) for paragraph in paragraph_payloads],
        )
        self._ensure_not_cancelled(is_cancel_requested)

        source_metadata = {
            **dict(item.get("metadata", {})),
            "job_id": job_id,
            "file_id": file_id,
            "detected_strategy": strategy,
            "source_file_type": file_type,
            **(dict(spreadsheet_bundle.get("metadata", {})) if spreadsheet_bundle is not None else {}),
            **({"spreadsheet_sheets": sheet_names} if sheet_names else {}),
        }
        source = self.source_store.create_source(
            name=source_name,
            source_kind=str(item["source_kind"]),
            input_mode=str(item["input_mode"]),
            file_type=file_type,
            storage_path=item.get("storage_path"),
            strategy=strategy,
            status="running",
            summary=None,
            metadata=source_metadata,
        )
        logger.info(
            "已创建来源记录：job_id=%s file_id=%s source_id=%s source_name=%s",
            job_id,
            file_id,
            str(source["id"]),
            source_name,
        )
        self.job_store.update_job_file(file_id, source_id=str(source["id"]), current_step="indexing", progress=18.0)
        on_progress(18.0, "indexing", f"正在写入来源记录：{source_name}")

        paragraph_rows = self.source_store.add_paragraphs(source_id=str(source["id"]), paragraphs=paragraph_payloads)
        self.record_store.sync_rows_for_paragraphs(paragraph_rows)
        self._ensure_not_cancelled(is_cancel_requested)

        self.job_store.update_job_file(file_id, current_step="embedding", progress=36.0)
        on_progress(36.0, "embedding", f"正在为 {len(paragraph_rows)} 个段落生成向量")
        logger.debug(
            "导入向量生成开始：job_id=%s file_id=%s source_id=%s paragraph_count=%s total_char_count=%s",
            job_id,
            file_id,
            str(source["id"]),
            len(paragraph_rows),
            sum(len(str(paragraph["content"])) for paragraph in paragraph_rows),
        )
        embeddings = self.gateway.generate_embeddings([str(paragraph["content"]) for paragraph in paragraph_rows])
        logger.debug(
            "导入向量生成完成：job_id=%s file_id=%s source_id=%s vector_count=%s dimension=%s",
            job_id,
            file_id,
            str(source["id"]),
            len(embeddings),
            len(embeddings[0]) if embeddings else 0,
        )
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
            self.source_store.update_paragraph(str(paragraph["id"]), vector_state="ready")
        self.vector.add_embeddings(
            model_signature=self.model_config_service.embedding_model_signature(),
            records=vector_records,
            embeddings=embeddings,
        )
        logger.info(
            "已写入向量索引：job_id=%s file_id=%s source_id=%s paragraph_count=%s",
            job_id,
            file_id,
            str(source["id"]),
            len(paragraph_rows),
        )
        self._ensure_not_cancelled(is_cancel_requested)

        extraction_result: dict[str, Any]
        extraction_warning: str | None = None
        if spreadsheet_bundle is not None:
            logger.info(
                "使用表格导入包中的实体关系数据：job_id=%s file_id=%s entity_count=%s relation_count=%s",
                job_id,
                file_id,
                len(list(spreadsheet_bundle.get("entities") or [])),
                len(list(spreadsheet_bundle.get("relations") or [])),
            )
            extraction_result = {
                "entities": list(spreadsheet_bundle.get("entities", [])),
                "relations": list(spreadsheet_bundle.get("relations", [])),
            }
        elif item.get("structured_entities") or item.get("structured_relations"):
            logger.info(
                "使用请求内提供的实体关系数据：job_id=%s file_id=%s entity_count=%s relation_count=%s",
                job_id,
                file_id,
                len(list(item.get("structured_entities") or [])),
                len(list(item.get("structured_relations") or [])),
            )
            extraction_result = {
                "entities": list(item.get("structured_entities", [])),
                "relations": list(item.get("structured_relations", [])),
            }
        else:
            extraction_result, extraction_warning = self._extract_document_graph(
                document_name=source_name,
                paragraph_rows=paragraph_rows,
                file_id=file_id,
                on_progress=on_progress,
                is_cancel_requested=is_cancel_requested,
            )
            if extraction_warning is None:
                logger.info(
                    "模型实体关系抽取完成：job_id=%s file_id=%s entity_count=%s relation_count=%s",
                    job_id,
                    file_id,
                    len(list(extraction_result.get("entities") or [])),
                    len(list(extraction_result.get("relations") or [])),
                )
        self._ensure_not_cancelled(is_cancel_requested)

        self.job_store.update_job_file(file_id, current_step="writing", progress=84.0)
        on_progress(84.0, "writing", f"正在写入图谱数据：{source_name}")
        self._write_entities_and_relations(
            source_id=str(source["id"]),
            paragraph_rows=paragraph_rows,
            extraction_result=extraction_result,
        )
        for chunk_row, paragraph_row in zip(chunk_rows, paragraph_rows, strict=True):
            self.job_store.update_job_chunk(
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
        if extraction_warning:
            summary = f"{summary}; extraction warning: {extraction_warning}"
        final_source_metadata = {
            **dict(source["metadata"]),
            "paragraph_count": len(paragraph_rows),
            "entity_count": len(extraction_result["entities"]),
            "relation_count": len(extraction_result["relations"]),
            "entity_extraction_status": "partial" if extraction_warning else "completed",
        }
        final_file_metadata = {
            **import_file_metadata,
            "paragraph_count": len(paragraph_rows),
            "entity_count": len(extraction_result["entities"]),
            "relation_count": len(extraction_result["relations"]),
            "entity_extraction_status": "partial" if extraction_warning else "completed",
        }
        if extraction_warning:
            final_source_metadata["entity_extraction_warning"] = extraction_warning
            final_file_metadata["entity_extraction_warning"] = extraction_warning
        self.source_store.update_source(
            str(source["id"]),
            status="partial" if extraction_warning else "ready",
            summary=summary,
            metadata=final_source_metadata,
        )
        self.job_store.update_job_file(
            file_id,
            status="partial" if extraction_warning else "completed",
            current_step="completed",
            progress=100.0,
            metadata=final_file_metadata,
            error=extraction_warning,
        )
        if extraction_warning:
            on_progress(100.0, "completed", f"导入完成，但实体抽取存在告警：{source_name}")
            logger.warning(
                "导入文件完成，但实体抽取存在告警：job_id=%s file_id=%s source_id=%s "
                "paragraph_count=%s entity_count=%s relation_count=%s warning=%s",
                job_id,
                file_id,
                str(source["id"]),
                len(paragraph_rows),
                len(extraction_result["entities"]),
                len(extraction_result["relations"]),
                extraction_warning,
            )
        else:
            on_progress(100.0, "completed", f"导入完成：{source_name}")
            logger.info(
                "导入文件完成：job_id=%s file_id=%s source_id=%s paragraph_count=%s entity_count=%s relation_count=%s",
                job_id,
                file_id,
                str(source["id"]),
                len(paragraph_rows),
                len(extraction_result["entities"]),
                len(extraction_result["relations"]),
            )
        return str(source["id"])

    def _resolve_text(
        self,
        *,
        item: dict[str, Any],
        spreadsheet_document: SpreadsheetDocumentData | None = None,
    ) -> str:
        """解析导入项文本内容。

        Args:
            item: 归一化导入项。
            spreadsheet_document: 解析后的表格文档对象。

        Returns:
            str: 可用于分块与抽取的文本内容。
        """

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
        """按文件类型解析电子表格文档。

        Args:
            item: 归一化导入项。
            file_type: 文件类型。

        Returns:
            SpreadsheetDocumentData | None: 表格文档对象，不支持或无路径时返回 None。
        """

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
        """构建段落写入载荷。

        Args:
            raw_text: 原始文本。
            item: 导入项。
            strategy: 分块策略。
            source_file_type: 来源文件类型。
            spreadsheet_bundle: 表格导入结构化结果。

        Returns:
            list[dict[str, Any]]: 段落载荷列表。
        """

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
    ) -> tuple[dict[str, Any], str | None]:
        """执行文档图谱抽取。

        Args:
            document_name: 文档名称。
            paragraph_rows: 段落行列表。
            file_id: 文件 ID。
            on_progress: 进度回调。
            is_cancel_requested: 取消检查函数。

        Returns:
            tuple[dict[str, Any], str | None]: 抽取结果与告警信息。

        Raises:
            ImportCancelledError: 当任务被取消时抛出。
        """

        windows = _build_extraction_windows([str(paragraph["content"]) for paragraph in paragraph_rows])
        logger.info(
            "开始分窗口执行实体关系抽取：document_name=%s file_id=%s paragraph_count=%s window_count=%s",
            document_name,
            file_id,
            len(paragraph_rows),
            len(windows),
        )
        logger.debug(
            "实体关系抽取窗口明细：document_name=%s file_id=%s windows=%s",
            document_name,
            file_id,
            [
                {
                    "index": window.index,
                    "chunk_count": len(window.chunk_indexes),
                    "text_length": len(window.text),
                    "token_count": count_tokens(window.text),
                }
                for window in windows
            ],
        )
        partial_results: list[dict[str, Any]] = []
        extraction_warning: str | None = None
        for window_index, window in enumerate(windows, start=1):
            self._ensure_not_cancelled(is_cancel_requested)
            total_windows = len(windows)
            progress_ratio = max(0.0, min((window_index - 1) / max(total_windows, 1), 1.0))
            file_progress = round(52.0 + 30.0 * progress_ratio, 2)
            self.job_store.update_job_file(file_id, current_step="extracting", progress=file_progress)
            on_progress(file_progress, "extracting", f"{document_name} 正在抽取实体关系：{window_index}/{total_windows}")
            logger.debug(
                "实体关系抽取窗口开始：document_name=%s file_id=%s window_index=%s total_windows=%s chunk_count=%s text_length=%s token_count=%s",
                document_name,
                file_id,
                window_index,
                total_windows,
                len(window.chunk_indexes),
                len(window.text),
                count_tokens(window.text),
            )
            try:
                partial_result = self.gateway.extract_document_graph(
                    document_name=document_name,
                    text=window.text,
                    window_label=f"window-{window.index}",
                )
                partial_results.append(partial_result)
                logger.debug(
                    "实体关系抽取窗口完成：document_name=%s file_id=%s window_index=%s entity_count=%s relation_count=%s",
                    document_name,
                    file_id,
                    window_index,
                    len(list(partial_result.get("entities") or [])),
                    len(list(partial_result.get("relations") or [])),
                )
            except ImportCancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                extraction_warning = (
                    f"实体关系抽取在第 {window_index}/{total_windows} 个窗口失败，"
                    f"已保留文本、向量和已完成的抽取结果：{exc}"
                )
                logger.exception(
                    "实体关系抽取窗口失败：document_name=%s file_id=%s window_index=%s total_windows=%s",
                    document_name,
                    file_id,
                    window_index,
                    total_windows,
                )
                break
        return _merge_extraction_results(partial_results), extraction_warning

    def _write_entities_and_relations(
        self,
        *,
        source_id: str,
        paragraph_rows: list[dict[str, Any]],
        extraction_result: dict[str, Any],
    ) -> None:
        """写入实体、关系及段落实体/关系关联。

        Args:
            source_id: 来源 ID。
            paragraph_rows: 段落行列表。
            extraction_result: 抽取结果。
        """

        entity_rows: dict[str, dict[str, Any]] = {}
        paragraph_text_map = {str(paragraph["id"]): str(paragraph["content"]) for paragraph in paragraph_rows}
        for entity in extraction_result["entities"]:
            row = self.graph_store.upsert_entity(
                display_name=str(entity["name"]),
                description=str(entity.get("description") or ""),
                metadata={**dict(entity.get("metadata", {})), "source_id": source_id},
            )
            entity_rows[str(entity["name"]).strip().lower()] = row
            for paragraph in paragraph_rows:
                mention_count = self._match_count(str(entity["name"]), str(paragraph["content"]))
                if mention_count <= 0:
                    continue
                self.graph_store.link_paragraph_entity(
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
            relation_row = self.graph_store.create_relation(
                subject_entity_id=str(subject_row["id"]),
                predicate=str(relation["predicate"]),
                object_entity_id=str(object_row["id"]),
                confidence=float(relation.get("confidence") or 1.0),
                source_paragraph_id=source_paragraph_id,
                metadata={**dict(relation.get("metadata", {})), "source_id": source_id},
            )
            if source_paragraph_id:
                self.graph_store.link_paragraph_relation(
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
        """定位关系对应的来源段落。

        Args:
            paragraph_rows: 段落行列表。
            subject: 关系主语。
            object_name: 关系宾语。
            paragraph_text_map: 段落 ID 到文本映射。

        Returns:
            str | None: 命中的段落 ID，未命中时返回 None。
        """

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
        """统计实体在段落中的命中次数。

        Args:
            entity_name: 实体名称。
            content: 段落内容。

        Returns:
            int: 命中次数。
        """

        normalized_name = entity_name.strip().lower()
        if not normalized_name:
            return 0
        return max(content.lower().count(normalized_name), 0)

    def _ensure_not_cancelled(self, is_cancel_requested: CancelChecker) -> None:
        """在收到取消信号时中断流程。

        Args:
            is_cancel_requested: 取消检查函数。

        Raises:
            ImportCancelledError: 当任务被取消时抛出。
        """

        if is_cancel_requested():
            raise ImportCancelledError("导入任务已被取消。")


class ImportExecutor:
    """导入任务线程执行器。

    Attributes:
        job_store (ImportJobStore): 导入任务仓储。
        pipeline (ImportPipeline): 导入处理流水线。
        _threads (dict[str, Thread]): 任务线程映射。
        _cancellations (dict[str, Event]): 任务取消标记映射。
        _lock (Lock): 并发保护锁。
    """

    def __init__(self, *, job_store: ImportJobStore, pipeline: ImportPipeline) -> None:
        """初始化导入执行器。

        Args:
            job_store: 导入任务仓储。
            pipeline: 导入流水线。
        """

        self.job_store = job_store
        self.pipeline = pipeline
        self._threads: dict[str, Thread] = {}
        self._cancellations: dict[str, Event] = {}
        self._lock = Lock()

    def submit(self, *, job_id: str, items: list[dict[str, Any]]) -> None:
        """提交导入任务到后台线程执行。

        Args:
            job_id: 导入任务 ID。
            items: 导入项列表。
        """

        logger.info("提交导入任务到执行器：job_id=%s item_count=%s", job_id, len(items))
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
        """标记指定导入任务为取消状态。

        Args:
            job_id: 导入任务 ID。
        """

        logger.info("请求取消导入任务：job_id=%s", job_id)
        with self._lock:
            cancellation_event = self._cancellations.get(job_id)
        if cancellation_event is not None:
            cancellation_event.set()

    def _run_job(self, *, job_id: str, items: list[dict[str, Any]], cancellation_event: Event) -> None:
        """执行导入任务主循环。

        Args:
            job_id: 导入任务 ID。
            items: 导入项列表。
            cancellation_event: 取消事件对象。
        """

        file_rows = self.job_store.list_job_files(job_id)
        had_success = False
        try:
            logger.info("导入任务开始执行：job_id=%s file_count=%s", job_id, len(file_rows))
            self.job_store.update_job(
                job_id,
                status="running",
                current_step="preparing",
                started_at=utc_now_iso(),
                message="开始执行导入任务",
            )
            for file_index, (file_row, item) in enumerate(zip(file_rows, items, strict=True)):
                file_id = str(file_row["id"])
                try:
                    logger.info(
                        "开始执行导入文件：job_id=%s file_id=%s file_index=%s file_name=%s",
                        job_id,
                        file_id,
                        file_index,
                        str(file_row.get("name") or item.get("name") or ""),
                    )
                    source_id = self.pipeline.process_item(
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
                    logger.info(
                        "导入文件执行完成：job_id=%s file_id=%s source_id=%s",
                        job_id,
                        file_id,
                        source_id,
                    )
                except ImportCancelledError as exc:
                    logger.warning("导入任务在处理文件时被取消：job_id=%s file_id=%s", job_id, file_id)
                    self._mark_file_cancelled(file_id=file_id, job_id=job_id, error_message=str(exc))
                    self.job_store.update_job(
                        job_id,
                        status="cancelled",
                        current_step="cancelled",
                        finished_at=utc_now_iso(),
                        message="导入任务已取消",
                        error=str(exc),
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "导入文件执行失败：job_id=%s file_id=%s file_name=%s",
                        job_id,
                        file_id,
                        str(file_row.get("name") or item.get("name") or ""),
                    )
                    self.job_store.update_job_file(
                        file_id,
                        status="failed",
                        current_step="failed",
                        error=str(exc),
                    )
                    for chunk_row in self.job_store.list_job_chunks(job_id, file_id):
                        self.job_store.update_job_chunk(
                            str(chunk_row["id"]),
                            status="failed",
                            step="failed",
                            error=str(exc),
                        )
            self.job_store.refresh_job_counters(job_id)
            latest_files = self.job_store.list_job_files(job_id)
            failed_files = sum(
                1 for file_row in latest_files if str(file_row.get("status") or "") in {"failed", "cancelled", "aborted"}
            )
            partial_files = sum(1 for file_row in latest_files if str(file_row.get("status") or "") == "partial")
            final_status = "completed"
            if failed_files > 0:
                final_status = "partial" if had_success else "failed"
            elif partial_files > 0:
                final_status = "partial"
            final_error = next(
                (str(file_row.get("error") or "") for file_row in latest_files if str(file_row.get("error") or "").strip()),
                None,
            )
            self.job_store.update_job(
                job_id,
                status=final_status,
                current_step="failed" if final_status == "failed" else "completed",
                progress=100.0,
                finished_at=utc_now_iso(),
                message=(
                    "导入完成"
                    if final_status == "completed"
                    else "导入完成，但存在告警"
                    if final_status == "partial"
                    else "导入失败"
                ),
                error=None if final_status == "completed" else final_error,
            )
            logger.info(
                "导入任务执行结束：job_id=%s status=%s failed_files=%s partial_files=%s succeeded=%s",
                job_id,
                final_status,
                failed_files,
                partial_files,
                had_success,
            )
        finally:
            if not had_success and cancellation_event.is_set():
                self.job_store.update_job(job_id, status="cancelled", current_step="cancelled", finished_at=utc_now_iso())
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
        """更新任务总体进度。

        Args:
            job_id: 任务 ID。
            file_index: 当前文件索引。
            total_files: 文件总数。
            file_progress: 当前文件进度。
            current_step: 当前步骤。
            message: 进度消息。
        """

        overall_progress = round(((file_index + file_progress / 100.0) / max(total_files, 1)) * 100.0, 2)
        self.job_store.update_job(
            job_id,
            status="running",
            current_step=current_step,
            progress=overall_progress,
            message=message,
        )

    def _mark_file_cancelled(self, *, file_id: str, job_id: str, error_message: str) -> None:
        """将文件及其分块标记为取消。

        Args:
            file_id: 文件 ID。
            job_id: 任务 ID。
            error_message: 取消原因。
        """

        self.job_store.update_job_file(
            file_id,
            status="cancelled",
            current_step="cancelled",
            error=error_message,
        )
        for chunk_row in self.job_store.list_job_chunks(job_id, file_id):
            self.job_store.update_job_chunk(
                str(chunk_row["id"]),
                status="cancelled",
                step="cancelled",
                error=error_message,
            )


class ImportService:
    """导入任务提交与编排服务。

    Attributes:
        settings (Settings): 全局配置对象。
        job_store (ImportJobStore): 导入任务仓储。
        executor (ImportExecutor): 导入执行器。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        job_store: ImportJobStore,
        executor: ImportExecutor,
    ) -> None:
        """初始化导入服务。

        Args:
            settings: 全局配置对象。
            job_store: 任务仓储。
            executor: 导入执行器。
        """

        self.settings = settings
        self.job_store = job_store
        self.executor = executor

    def submit_uploads(self, *, files: list[tuple[str, bytes, str | None]], strategy: str) -> dict[str, Any]:
        """提交上传文件导入任务。

        Args:
            files: 上传文件列表，元素为 (文件名, 二进制内容, Content-Type)。
            strategy: 分块策略。

        Returns:
            dict[str, Any]: 导入任务详情。

        Raises:
            ValueError: 当上传文件为空或无可导入文件时抛出。
        """

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
        logger.info(
            "收到上传导入请求：uploaded_count=%s data_file_count=%s sidecar_count=%s strategy=%s",
            len(files),
            len(data_files),
            len(schema_by_stem),
            strategy,
        )
        if not data_files:
            raise ValueError("没有检测到可导入的文档或表格文件。")
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
        """提交粘贴文本导入任务。

        Args:
            title: 来源标题。
            content: 文本内容。
            strategy: 分块策略。
            metadata: 额外元数据。

        Returns:
            dict[str, Any]: 导入任务详情。

        Raises:
            ValueError: 当粘贴内容为空时抛出。
        """

        normalized_title = str(title or "").strip() or "粘贴文本"
        normalized_content = str(content or "").strip()
        if not normalized_content:
            raise ValueError("粘贴内容不能为空。")
        item = build_text_import_item(
            name=normalized_title,
            text=normalized_content,
            source_kind="paste",
            input_mode="text",
            strategy=strategy,
            metadata=dict(metadata or {}),
        )
        logger.info(
            "收到粘贴导入请求：title=%s content_length=%s strategy=%s",
            normalized_title,
            len(normalized_content),
            strategy,
        )
        return self._create_job(source="paste", input_mode="text", strategy=strategy, items=[item])

    def submit_scan(self, *, root_path: str, glob_pattern: str, strategy: str) -> dict[str, Any]:
        """扫描目录并批量提交文件导入任务。

        Args:
            root_path: 扫描根目录。
            glob_pattern: 文件匹配模式。
            strategy: 分块策略。

        Returns:
            dict[str, Any]: 导入任务详情。

        Raises:
            ValueError: 当路径不合法或未扫描到可导入文件时抛出。
        """

        root = Path(root_path).resolve()
        allowed_roots = [path for path in self.settings.resolved_kb_scan_roots if path.exists()]
        if allowed_roots and not any(root.is_relative_to(allowed_root) for allowed_root in allowed_roots):
            raise ValueError("扫描路径不在允许的根目录范围内。")
        if not root.exists() or not root.is_dir():
            raise ValueError("扫描路径必须是已存在的目录。")
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
                raise ValueError(f"没有找到受支持的文件类型，支持的格式有：{SUPPORTED_EXTENSION_DISPLAY}")
            raise ValueError("扫描路径下没有匹配当前模式的文件。")
        logger.info(
            "收到扫描导入请求：root=%s pattern=%s matched_count=%s skipped_unsupported_count=%s strategy=%s",
            str(root),
            normalized_pattern,
            len(items),
            skipped_unsupported_count,
            strategy,
        )
        return self._create_job(source="scan", input_mode="file", strategy=strategy, items=items)

    def submit_openie(
        self,
        *,
        title: str,
        payload: dict[str, Any],
        strategy: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """提交 OpenIE 结构化导入任务。

        Args:
            title: 来源标题。
            payload: 结构化载荷。
            strategy: 分块策略。
            metadata: 额外元数据。

        Returns:
            dict[str, Any]: 导入任务详情。
        """

        item = build_structured_import_item(
            name=str(title or "").strip() or "OpenIE 导入",
            payload=payload,
            source_kind="openie",
            input_mode="json",
            strategy=strategy,
            metadata=dict(metadata or {}),
        )
        logger.info(
            "收到 OpenIE 导入请求：title=%s strategy=%s has_entities=%s has_relations=%s",
            str(title or "").strip() or "OpenIE 导入",
            strategy,
            bool(list(payload.get("entities") or [])),
            bool(list(payload.get("relations") or [])),
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
        """提交转换后结构化导入任务。

        Args:
            title: 来源标题。
            payload: 转换后的结构化载荷。
            strategy: 分块策略。
            metadata: 额外元数据。

        Returns:
            dict[str, Any]: 导入任务详情。
        """

        item = build_structured_import_item(
            name=str(title or "").strip() or "转换结果导入",
            payload=payload,
            source_kind="convert",
            input_mode="json",
            strategy=strategy,
            metadata=dict(metadata or {}),
        )
        logger.info(
            "收到转换结果导入请求：title=%s strategy=%s has_paragraphs=%s has_entities=%s has_relations=%s",
            str(title or "").strip() or "转换结果导入",
            strategy,
            bool(list(payload.get("paragraphs") or [])),
            bool(list(payload.get("entities") or [])),
            bool(list(payload.get("relations") or [])),
        )
        return self._create_job(source="convert", input_mode="json", strategy=strategy, items=[item])

    def list_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """按时间倒序返回导入任务列表。

        Args:
            limit: 最大返回数量。

        Returns:
            list[dict[str, Any]]: 导入任务列表。
        """

        return [self.job_store.hydrate_job(job) for job in self.job_store.list_jobs(limit=limit)]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """读取单个导入任务详情。

        Args:
            job_id: 导入任务 ID。

        Returns:
            dict[str, Any] | None: 任务详情，不存在时返回 None。
        """

        job = self.job_store.get_job(job_id)
        if job is None:
            return None
        return self.job_store.hydrate_job(job)

    def list_job_chunks(self, job_id: str, file_id: str) -> list[dict[str, Any]]:
        """列出指定文件的分块处理记录。

        Args:
            job_id: 导入任务 ID。
            file_id: 导入文件 ID。

        Returns:
            list[dict[str, Any]]: 分块记录列表。
        """

        if self.job_store.get_job(job_id) is None:
            return []
        return self.job_store.list_job_chunks(job_id, file_id)

    def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        """取消指定导入任务并返回最新状态。

        Args:
            job_id: 导入任务 ID。

        Returns:
            dict[str, Any] | None: 更新后的任务详情，不存在时返回 None。
        """

        job = self.job_store.get_job(job_id)
        if job is None:
            return None
        self.executor.cancel(job_id)
        updated_job = self.job_store.update_job(
            job_id,
            status="cancelled",
            current_step="cancelled",
            finished_at=utc_now_iso(),
            message="导入任务已取消。",
        )
        return self.job_store.hydrate_job(updated_job) if updated_job is not None else None

    def retry_failed(self, job_id: str) -> dict[str, Any]:
        """重试指定任务中失败或部分失败的文件。

        Args:
            job_id: 导入任务 ID。

        Returns:
            dict[str, Any]: 新建的重试任务详情。

        Raises:
            ValueError: 当任务不存在或无可重试文件时抛出。
        """

        job = self.get_job(job_id)
        if job is None:
            raise ValueError("未找到导入任务。")
        failed_items: list[dict[str, Any]] = []
        for file_row in list(job.get("files") or []):
            if str(file_row.get("status") or "") not in {"failed", "partial"}:
                continue
            retry_payload = dict(file_row.get("metadata", {})).get("retry_payload")
            if isinstance(retry_payload, dict):
                failed_items.append(retry_payload)
        if not failed_items:
            raise ValueError("当前导入任务没有可重试的失败文件或部分失败文件。")
        logger.info("开始重试异常导入文件：job_id=%s retry_count=%s", job_id, len(failed_items))
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
        """创建并派发导入任务。

        Args:
            source: 任务来源。
            input_mode: 输入模式。
            strategy: 分块策略。
            items: 导入项列表。

        Returns:
            dict[str, Any]: 导入任务详情。

        Raises:
            ValueError: 当导入项为空时抛出。
        """

        if not items:
            raise ValueError("当前操作没有生成可导入的数据项。")
        job = self.job_store.create_job(
            source=source,
            input_mode=input_mode,
            strategy=strategy,
            params={"source": source, "input_mode": input_mode, "strategy": strategy},
            total_files=len(items),
        )
        logger.info(
            "已创建导入任务：job_id=%s source=%s input_mode=%s strategy=%s file_count=%s",
            str(job["id"]),
            source,
            input_mode,
            strategy,
            len(items),
        )
        for item in items:
            self.job_store.create_job_file(
                job_id=str(job["id"]),
                name=str(item["name"]),
                source_kind=str(item["source_kind"]),
                input_mode=str(item["input_mode"]),
                strategy=strategy,
                storage_path=item.get("storage_path"),
                metadata={**dict(item.get("metadata", {})), "retry_payload": item},
            )
        self.executor.submit(job_id=str(job["id"]), items=items)
        logger.info("导入任务已派发到执行器：job_id=%s", str(job["id"]))
        return self.get_job(str(job["id"])) or job

    def _normalize_upload_file(
        self,
        *,
        original_name: str,
        content_type: str | None,
        contents: bytes,
    ) -> dict[str, Any]:
        """归一化上传文件信息并识别文件类型。

        Args:
            original_name: 原始文件名。
            content_type: 内容类型。
            contents: 文件二进制内容。

        Returns:
            dict[str, Any]: 归一化后的文件信息。

        Raises:
            ValueError: 当文件类型不受支持时抛出。
        """

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
        """收集上传中的表格侧车 Schema。

        Args:
            normalized_files: 归一化文件列表。

        Returns:
            dict[str, dict[str, Any]]: 以工作簿 stem 为键的 Schema 映射。
        """

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
        """为上传文件附加侧车 Schema。

        Args:
            item: 导入项。
            normalized_file: 归一化文件信息。
            schema_by_stem: Schema 映射。
        """

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
        """为扫描文件附加同名侧车 Schema。

        Args:
            item: 导入项。
            file_path: 文件路径。
            file_type: 文件类型。
        """

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
    """将段落序列按 token 限制切分为抽取窗口。

    Args:
        paragraph_texts: 段落文本列表。
        max_tokens: 单个窗口允许的最大 token 数。

    Returns:
        list[ExtractionWindow]: 抽取窗口列表。
    """

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
    """合并多窗口抽取结果并去重。

    Args:
        partial_results: 多个窗口的抽取结果。

    Returns:
        dict[str, Any]: 合并后的 entities 与 relations。
    """

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





