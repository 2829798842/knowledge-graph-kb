"""模块名称：services.ingestion_service

主要功能：串联文件解析、自然分段、嵌入生成、实体抽取与图谱写入流程。
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
from src.services.entity_extraction_service import EntityExtractionService
from src.services.graph_service import (
    create_chunk_graph,
    create_entity_graph,
    create_semantic_edges,
    seed_document_node,
)
from src.services.openai_service import OpenAiService
from src.services.parser_service import extract_text
from src.services.vector_store_service import FaissVectorStore, VectorRecord


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
            return

        try:
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

            self._update_job_progress(
                session,
                document=document,
                job=job,
                status=JobStatus.PROCESSING,
                document_status=DocumentStatus.PROCESSING,
                stage="extracting",
                progress_percent=68,
                status_message="正在调用 LLM 抽取实体与关系",
            )
            extraction = self.entity_extraction_service.extract_document_graph(
                document_name=document.original_name,
                chunk_texts=chunk_texts,
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
            document.summary = f"{len(chunk_rows)} 个片段，{len(extraction.entities)} 个实体"
            document.metadata_json = {
                **document.metadata_json,
                "chunk_count": len(chunk_rows),
                "entity_count": len(extraction.entities),
                "relation_count": len(extraction.relations),
                "last_processed_at": finished_at.isoformat(),
            }
            document.updated_at = finished_at
            seed_document_node(session, document)

            job.status = JobStatus.COMPLETED
            job.progress_percent = 100
            job.stage = "completed"
            job.status_message = "抽取完成，图谱与索引已更新"
            job.error_message = None
            job.updated_at = finished_at
            session.add(document)
            session.add(job)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
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

        entity_nodes: list[GraphNode] = list(session.exec(select(GraphNode).where(GraphNode.node_type == NodeType.ENTITY)).all())
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
        """

        updated_at = utc_now()
        document.status = document_status
        document.updated_at = updated_at
        job.status = status
        job.stage = stage
        job.progress_percent = max(0, min(progress_percent, 100))
        job.status_message = status_message
        job.updated_at = updated_at
        session.add(document)
        session.add(job)
        session.commit()

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
            job.status_message = error_message
            job.error_message = error_message
            job.updated_at = updated_at
            session.add(job)
        session.commit()
