"""模块名称：services.ingestion_service

主要功能：串联文件解析、切块、嵌入、实体抽取与图谱写入流程。
"""

from pathlib import Path

from sqlmodel import Session, select

from src.config import Settings
from src.data import Chunk, Document, DocumentStatus, IngestionJob, JobStatus, chunk_node_id
from src.services.chunking_service import count_tokens, split_text
from src.services.entity_extraction_service import EntityExtractionService
from src.services.graph_service import create_chunk_graph, create_entity_graph, create_semantic_edges
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
        """处理单个文档的全量导入流程。

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
            document.status = DocumentStatus.PROCESSING
            job.status = JobStatus.PROCESSING
            session.add(document)
            session.add(job)
            session.commit()

            raw_text: str = extract_text(Path(document.storage_path))
            chunks: list[str] = split_text(
                raw_text,
                max_tokens=self.settings.chunk_size_tokens,
                overlap_tokens=self.settings.chunk_overlap_tokens,
            )
            if not chunks:
                raise ValueError("The uploaded file did not contain any extractable text.")

            chunk_rows: list[Chunk] = self._replace_chunks(session, document=document, chunks=chunks)
            embeddings: list[list[float]] = self.openai_service.embed_texts([chunk.text for chunk in chunk_rows])
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

            extraction = self.entity_extraction_service.extract_document_graph(
                document_name=document.original_name,
                chunk_texts=[chunk.text for chunk in chunk_rows],
            )
            create_chunk_graph(session, document=document, chunks=chunk_rows)
            create_entity_graph(session, document=document, chunks=chunk_rows, extraction=extraction)
            create_semantic_edges(
                session,
                vector_store=self.vector_store,
                chunk_vectors=vector_records,
                threshold=self.settings.graph_similarity_threshold,
            )

            document.status = DocumentStatus.READY
            document.summary = f"{len(chunk_rows)} chunks, {len(extraction.entities)} entities"
            document.metadata_json = {
                **document.metadata_json,
                "chunk_count": len(chunk_rows),
                "entity_count": len(extraction.entities),
                "relation_count": len(extraction.relations),
            }
            job.status = JobStatus.COMPLETED
            job.error_message = None
            session.add(document)
            session.add(job)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            self._mark_failed(session, job_id=job_id, document_id=document_id, error_message=str(exc))

    def _replace_chunks(self, session: Session, *, document: Document, chunks: list[str]) -> list[Chunk]:
        """替换文档现有切块并写入新切块。

        Args:
            session: 数据库会话。
            document: 文档模型。
            chunks: 切块文本列表。

        Returns:
            list[Chunk]: 写入后的切块模型列表。
        """

        existing_chunks: list[Chunk] = session.exec(select(Chunk).where(Chunk.document_id == document.id)).all()
        for chunk in existing_chunks:
            session.delete(chunk)
        session.flush()

        chunk_rows: list[Chunk] = []
        for chunk_index, chunk_text in enumerate(chunks):
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
        session.commit()
        for chunk in chunk_rows:
            session.refresh(chunk)
        return chunk_rows

    def _mark_failed(self, session: Session, *, job_id: str, document_id: str, error_message: str) -> None:
        """将文档与任务标记为失败状态。

        Args:
            session: 数据库会话。
            job_id: 导入任务主键。
            document_id: 文档主键。
            error_message: 失败错误信息。
        """

        document = session.get(Document, document_id)
        job = session.get(IngestionJob, job_id)
        if document is not None:
            document.status = DocumentStatus.FAILED
            session.add(document)
        if job is not None:
            job.status = JobStatus.FAILED
            job.error_message = error_message
            session.add(job)
        session.commit()
