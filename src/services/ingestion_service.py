"""串联文档解析、自然分段、向量生成、实体抽取与图谱写入流程。
"""

from pathlib import Path

from sqlmodel import Session, select

from src.config import Settings
from src.data import (
    Chunk,
    Document,
    DocumentStatus,
    GraphEdge,
    GraphNode,
    IngestionJob,
    JobStatus,
    NodeType,
    chunk_node_id,
    utc_now,
)
from src.services.chunking_service import count_tokens, split_text
from src.services.entity_extraction_service import EntityExtractionService, ExtractionWindow
from src.services.graph_service import (
    create_chunk_graph,
    create_entity_graph,
    create_semantic_edges,
    seed_document_node,
)
from src.services.openai_service import OpenAiService
from src.services.parser_service import extract_text
from src.services.vector_store_service import FaissVectorStore, VectorRecord
from src.utils.logging_utils import get_logger

EXTRACTING_PROGRESS_START: int = 68
EXTRACTING_PROGRESS_END: int = 82
EXTRACTION_STARTED_PROGRESS_WEIGHT: float = 0.45

logger = get_logger(__name__)


class IngestionService:
    """文档导入服务。

    Attributes:
        settings (Settings): 当前应用配置。
        openai_service (OpenAiService): OpenAI 服务。
        entity_extraction_service (EntityExtractionService): 实体抽取服务。
        vector_store (FaissVectorStore): 向量存储服务。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        openai_service: OpenAiService,
        entity_extraction_service: EntityExtractionService,
        vector_store: FaissVectorStore,
    ) -> None:
        """初始化导入服务。

        Args:
            settings: 当前应用配置。
            openai_service: OpenAI 服务。
            entity_extraction_service: 实体抽取服务。
            vector_store: 向量存储服务。
        """

        self.settings: Settings = settings
        self.openai_service: OpenAiService = openai_service
        self.entity_extraction_service: EntityExtractionService = entity_extraction_service
        self.vector_store: FaissVectorStore = vector_store

    def process_document(self, session: Session, *, job_id: str, document_id: str) -> None:
        """处理单个文档的全量抽取流程。

        Args:
            session: 数据库会话。
            job_id: 导入任务主键。
            document_id: 文档主键。
        """

        document = session.get(Document, document_id)
        job = session.get(IngestionJob, job_id)
        if document is None or job is None:
            logger.warning("导入任务缺少有效文档或任务记录: job_id=%s document_id=%s", job_id, document_id)
            return

        try:
            logger.info("开始处理文档: job_id=%s document_id=%s original_name=%s", job.id, document.id, document.original_name)
            self._update_job_progress(
                session,
                document=document,
                job=job,
                status=JobStatus.PROCESSING,
                document_status=DocumentStatus.PROCESSING,
                stage="parsing",
                progress_percent=6,
                status_message="正在解析文档内容",
            )
            raw_text: str = extract_text(Path(document.storage_path))
            logger.info("文档解析完成: document_id=%s char_count=%s", document.id, len(raw_text))

            self._update_job_progress(
                session,
                document=document,
                job=job,
                status=JobStatus.PROCESSING,
                document_status=DocumentStatus.PROCESSING,
                stage="chunking",
                progress_percent=18,
                status_message="正在按自然段切分文本",
            )
            chunk_texts: list[str] = split_text(
                raw_text,
                max_tokens=self.settings.chunk_size_tokens,
                overlap_tokens=self.settings.chunk_overlap_tokens,
            )
            if not chunk_texts:
                raise ValueError("上传的文件中没有可提取的有效文本内容。")
            logger.info("文档切块完成: document_id=%s chunk_count=%s", document.id, len(chunk_texts))

            self._update_job_progress(
                session,
                document=document,
                job=job,
                status=JobStatus.PROCESSING,
                document_status=DocumentStatus.PROCESSING,
                stage="embedding",
                progress_percent=42,
                status_message=f"正在为 {len(chunk_texts)} 个片段生成向量",
            )
            embeddings: list[list[float]] = self.openai_service.embed_texts(chunk_texts)
            logger.info("向量生成完成: document_id=%s embedding_count=%s", document.id, len(embeddings))

            extraction_windows: list[ExtractionWindow] = self.entity_extraction_service.build_windows(chunk_texts)
            extraction_window_total: int = len([window for window in extraction_windows if window.text.strip()])
            logger.info("开始实体抽取: document_id=%s window_count=%s", document.id, extraction_window_total)
            self._update_job_progress(
                session,
                document=document,
                job=job,
                status=JobStatus.PROCESSING,
                document_status=DocumentStatus.PROCESSING,
                stage="extracting",
                progress_percent=EXTRACTING_PROGRESS_START,
                stage_current=0,
                stage_total=extraction_window_total,
                stage_unit="窗口",
                status_message=self._build_extraction_status_message(
                    current=0,
                    total=extraction_window_total,
                    event="started",
                ),
            )
            extraction = self.entity_extraction_service.extract_document_graph(
                document_name=document.original_name,
                chunk_texts=chunk_texts,
                windows=extraction_windows,
                progress_callback=lambda current, total, event: self._update_extraction_progress(
                    session,
                    document=document,
                    job=job,
                    current=current,
                    total=total,
                    event=event,
                ),
            )

            self._update_job_progress(
                session,
                document=document,
                job=job,
                status=JobStatus.PROCESSING,
                document_status=DocumentStatus.PROCESSING,
                stage="graph",
                progress_percent=82,
                status_message="正在更新图谱与检索索引",
            )
            logger.info(
                "开始写入图谱: document_id=%s chunk_count=%s entity_count=%s relation_count=%s",
                document.id,
                len(chunk_texts),
                len(extraction.entities),
                len(extraction.relations),
            )
            self._clear_document_artifacts(session, document=document)
            chunk_rows: list[Chunk] = self._write_chunks(session, document=document, chunk_texts=chunk_texts)
            vector_records: list[VectorRecord] = [
                VectorRecord(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    node_id=chunk.node_id,
                    text=chunk.text,
                    vector=embedding,
                )
                for chunk, embedding in zip(chunk_rows, embeddings, strict=True)
            ]
            self.vector_store.add_embeddings(vector_records)
            create_chunk_graph(session, document=document, chunks=chunk_rows)
            create_entity_graph(session, document=document, chunks=chunk_rows, extraction=extraction)
            create_semantic_edges(
                session,
                vector_store=self.vector_store,
                chunk_vectors=vector_records,
                threshold=self.settings.graph_similarity_threshold,
            )

            finished_at = utc_now()
            document.status = DocumentStatus.READY
            document.summary = (
                f"{len(chunk_rows)} 个片段，{len(extraction.entities)} 个实体，"
                f"{len(extraction.relations)} 条关系"
            )
            document.metadata_json = {
                **document.metadata_json,
                "chunk_count": len(chunk_rows),
                "entity_count": len(extraction.entities),
                "relation_count": len(extraction.relations),
                "extraction_window_count": extraction_window_total,
                "last_processed_at": finished_at.isoformat(),
            }
            document.updated_at = finished_at
            seed_document_node(session, document)

            job.status = JobStatus.COMPLETED
            job.progress_percent = 100
            job.stage = "completed"
            job.stage_current = 0
            job.stage_total = 0
            job.stage_unit = None
            job.status_message = "抽取完成，图谱与索引已更新"
            job.error_message = None
            job.updated_at = finished_at
            session.add(document)
            session.add(job)
            session.commit()
            logger.info(
                "文档处理完成: job_id=%s document_id=%s chunk_count=%s entity_count=%s relation_count=%s",
                job.id,
                document.id,
                len(chunk_rows),
                len(extraction.entities),
                len(extraction.relations),
            )
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.exception("文档处理失败: job_id=%s document_id=%s", job_id, document_id)
            self._mark_failed(session, job_id=job_id, document_id=document_id, error_message=str(exc))

    def _clear_document_artifacts(self, session: Session, *, document: Document) -> None:
        """清理文档旧的切块、图谱边与向量记录。

        Args:
            session: 数据库会话。
            document: 文档模型。
        """

        existing_chunks: list[Chunk] = list(session.exec(select(Chunk).where(Chunk.document_id == document.id)).all())
        chunk_node_ids: set[str] = {chunk.node_id for chunk in existing_chunks}
        graph_edges: list[GraphEdge] = list(session.exec(select(GraphEdge)).all())

        for edge in graph_edges:
            edge_metadata = edge.metadata_json if isinstance(edge.metadata_json, dict) else {}
            edge_document_id: str | None = edge_metadata.get("document_id")
            if (
                edge_document_id == document.id
                or edge.source_node_id in chunk_node_ids
                or edge.target_node_id in chunk_node_ids
            ):
                session.delete(edge)

        graph_nodes: list[GraphNode] = list(session.exec(select(GraphNode)).all())
        for node in graph_nodes:
            if node.id in chunk_node_ids:
                session.delete(node)

        for chunk in existing_chunks:
            session.delete(chunk)

        self.vector_store.remove_document(document.id)
        session.flush()
        self._remove_orphan_entity_nodes(session)

    def _remove_orphan_entity_nodes(self, session: Session) -> None:
        """删除已经没有任何边关联的孤立实体节点。

        Args:
            session: 数据库会话。
        """

        graph_edges: list[GraphEdge] = list(session.exec(select(GraphEdge)).all())
        referenced_node_ids: set[str] = set()
        for edge in graph_edges:
            referenced_node_ids.add(edge.source_node_id)
            referenced_node_ids.add(edge.target_node_id)

        entity_nodes: list[GraphNode] = list(
            session.exec(select(GraphNode).where(GraphNode.node_type == NodeType.ENTITY)).all()
        )
        for entity_node in entity_nodes:
            if entity_node.id not in referenced_node_ids:
                session.delete(entity_node)
        session.flush()

    def _write_chunks(self, session: Session, *, document: Document, chunk_texts: list[str]) -> list[Chunk]:
        """写入新的文档切块记录。

        Args:
            session: 数据库会话。
            document: 文档模型。
            chunk_texts: 切块文本列表。

        Returns:
            list[Chunk]: 已写入的切块模型列表。
        """

        chunk_rows: list[Chunk] = []
        for chunk_index, chunk_text in enumerate(chunk_texts):
            chunk = Chunk(
                document_id=document.id,
                node_id=chunk_node_id(f"{document.id}-{chunk_index}"),
                chunk_index=chunk_index,
                token_count=count_tokens(chunk_text),
                text=chunk_text,
                metadata_json={"document_id": document.id, "chunk_index": chunk_index},
            )
            session.add(chunk)
            chunk_rows.append(chunk)

        session.flush()
        for chunk in chunk_rows:
            session.refresh(chunk)
        return chunk_rows

    def _update_job_progress(
        self,
        session: Session,
        *,
        document: Document,
        job: IngestionJob,
        status: JobStatus,
        document_status: DocumentStatus,
        stage: str,
        progress_percent: int,
        status_message: str,
        stage_current: int = 0,
        stage_total: int = 0,
        stage_unit: str | None = None,
    ) -> None:
        """更新导入任务的阶段、进度与状态说明。

        Args:
            session: 数据库会话。
            document: 文档模型。
            job: 导入任务模型。
            status: 任务状态。
            document_status: 文档状态。
            stage: 当前处理阶段。
            progress_percent: 当前进度百分比。
            status_message: 面向前端展示的状态说明。
            stage_current: 当前阶段已处理到的子步骤序号。
            stage_total: 当前阶段总子步骤数。
            stage_unit: 当前阶段子步骤单位。
        """

        updated_at = utc_now()
        document.status = document_status
        document.updated_at = updated_at
        job.status = status
        job.stage = stage
        job.progress_percent = max(0, min(progress_percent, 100))
        job.stage_current = max(0, stage_current)
        job.stage_total = max(0, stage_total)
        job.stage_unit = stage_unit
        job.status_message = status_message
        job.updated_at = updated_at
        session.add(document)
        session.add(job)
        session.commit()

    def _update_extraction_progress(
        self,
        session: Session,
        *,
        document: Document,
        job: IngestionJob,
        current: int,
        total: int,
        event: str,
    ) -> None:
        """在 LLM 实体提取阶段按窗口回写细粒度进度。

        Args:
            session: 数据库会话。
            document: 文档模型。
            job: 导入任务模型。
            current: 当前窗口序号。
            total: 总窗口数。
            event: 进度事件，取值为 `started` 或 `completed`。
        """

        completed_units: float = self._resolve_extraction_progress_units(current=current, total=total, event=event)
        progress_percent: int = self._calculate_stage_progress(
            start=EXTRACTING_PROGRESS_START,
            end=EXTRACTING_PROGRESS_END,
            completed=completed_units,
            total=total,
        )
        self._update_job_progress(
            session,
            document=document,
            job=job,
            status=JobStatus.PROCESSING,
            document_status=DocumentStatus.PROCESSING,
            stage="extracting",
            progress_percent=progress_percent,
            status_message=self._build_extraction_status_message(current=current, total=total, event=event),
            stage_current=current,
            stage_total=total,
            stage_unit="窗口",
        )

    def _resolve_extraction_progress_units(self, *, current: int, total: int, event: str) -> float:
        """将抽取窗口事件映射为阶段内的进度单位。

        Args:
            current: 当前窗口序号。
            total: 总窗口数。
            event: 进度事件。

        Returns:
            float: 当前阶段的完成单位数。
        """

        if total <= 0:
            return 0.0
        if event == "completed":
            return float(current)
        if event == "started":
            return max(current - 1, 0) + EXTRACTION_STARTED_PROGRESS_WEIGHT
        return float(max(current - 1, 0))

    def _calculate_stage_progress(self, *, start: int, end: int, completed: float, total: int) -> int:
        """根据阶段内已完成的子步骤数量，计算总体进度。

        Args:
            start: 阶段起始进度。
            end: 阶段结束进度。
            completed: 已完成子步骤数量。
            total: 总子步骤数。

        Returns:
            int: 映射后的总体进度百分比。
        """

        if total <= 0:
            return start

        completed_ratio: float = max(0.0, min(completed / total, 1.0))
        return int(round(start + (end - start) * completed_ratio))

    def _build_extraction_status_message(self, *, current: int, total: int, event: str) -> str:
        """构建面向前端的 LLM 抽取进度文案。

        Args:
            current: 当前窗口序号。
            total: 总窗口数。
            event: 进度事件，取值为 `started` 或 `completed`。

        Returns:
            str: 前端展示文案。
        """

        if total <= 0:
            return "正在整理 LLM 抽取任务"

        if event == "completed" and current >= total:
            return "LLM 实体提取已完成，正在合并实体与关系"

        if event == "completed":
            return f"已完成第 {current}/{total} 个窗口，准备处理下一个窗口"

        next_window: int = max(1, min(current, total))
        return f"正在进行 LLM 实体提取（第 {next_window}/{total} 个窗口）"

    def _mark_failed(self, session: Session, *, job_id: str, document_id: str, error_message: str) -> None:
        """将文档与任务标记为失败状态。

        Args:
            session: 数据库会话。
            job_id: 导入任务主键。
            document_id: 文档主键。
            error_message: 失败错误信息。
        """

        updated_at = utc_now()
        document = session.get(Document, document_id)
        job = session.get(IngestionJob, job_id)
        if document is not None:
            document.status = DocumentStatus.FAILED
            document.updated_at = updated_at
            session.add(document)
        if job is not None:
            job.status = JobStatus.FAILED
            job.stage = "failed"
            job.stage_current = 0
            job.stage_total = 0
            job.stage_unit = None
            job.status_message = error_message
            job.error_message = error_message
            job.updated_at = updated_at
            session.add(job)
        session.commit()
