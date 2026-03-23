"""基于 FAISS 的向量存储实现，并提供本地元数据持久化。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from src.config import Settings, ensure_app_dirs


class VectorRecord:
    """与切块元数据一同持久化的向量记录。"""

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        node_id: str,
        text: str,
        vector: list[float],
    ) -> None:
        self.chunk_id: str = chunk_id
        self.document_id: str = document_id
        self.node_id: str = node_id
        self.text: str = text
        self.vector: list[float] = vector


class VectorSearchResult:
    """从 FAISS 索引返回的向量检索结果。"""

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        node_id: str,
        text: str,
        distance: float,
        similarity: float,
        vector: list[float],
    ) -> None:
        self.chunk_id: str = chunk_id
        self.document_id: str = document_id
        self.node_id: str = node_id
        self.text: str = text
        self.distance: float = distance
        self.similarity: float = similarity
        self.vector: list[float] = vector


class FaissVectorStore:
    """使用 FAISS 与 JSON 元数据在本地持久化嵌入向量。"""

    INDEX_FILENAME: str = "chunk_embeddings.index"
    METADATA_FILENAME: str = "chunk_embeddings.json"

    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        ensure_app_dirs(settings)

        self.store_dir: Path = settings.resolved_vector_store_dir
        self.index_path: Path = self.store_dir / self.INDEX_FILENAME
        self.metadata_path: Path = self.store_dir / self.METADATA_FILENAME
        self._metadata: list[dict[str, Any]] = []
        self._index: Any | None = None
        self._dimension: int | None = None

        self._load_state()

    def add_embeddings(self, records: list[VectorRecord]) -> None:
        """新增或覆盖切块嵌入向量，并重建 FAISS 索引。"""

        if not records:
            return

        record_map: dict[str, dict[str, Any]] = {item["chunk_id"]: item for item in self._metadata}
        for record in records:
            record_map[record.chunk_id] = {
                "chunk_id": record.chunk_id,
                "document_id": record.document_id,
                "node_id": record.node_id,
                "text": record.text,
                "vector": [float(value) for value in record.vector],
            }

        self._metadata = list(record_map.values())
        self._rebuild_index()
        self._persist_state()

    def search(
        self,
        query_vector: list[float],
        limit: int = 20,
        document_ids: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        """使用余弦相似度检索 FAISS 索引。"""

        if self._index is None or not self._metadata or limit <= 0:
            return []

        query_matrix: np.ndarray = self._normalize_vectors([query_vector])
        fetch_limit: int = self._search_limit(limit=limit, has_filter=bool(document_ids))
        if fetch_limit <= 0:
            return []

        similarities, indices = self._index.search(query_matrix, fetch_limit)
        allowed_documents: set[str] = set(document_ids or [])
        results: list[VectorSearchResult] = []

        for similarity, position in zip(similarities[0].tolist(), indices[0].tolist(), strict=True):
            if position < 0 or position >= len(self._metadata):
                continue

            payload: dict[str, Any] = self._metadata[position]
            if allowed_documents and payload["document_id"] not in allowed_documents:
                continue

            similarity_score: float = float(similarity)
            results.append(
                VectorSearchResult(
                    chunk_id=str(payload["chunk_id"]),
                    document_id=str(payload["document_id"]),
                    node_id=str(payload["node_id"]),
                    text=str(payload["text"]),
                    distance=1.0 - similarity_score,
                    similarity=similarity_score,
                    vector=[float(value) for value in payload["vector"]],
                )
            )
            if len(results) >= limit:
                break

        return results

    def reset(self) -> None:
        """清空所有已持久化向量，并将存储重置为空。"""

        self._metadata = []
        self._index = None
        self._dimension = None
        self._persist_state()

    def _load_state(self) -> None:
        """如果磁盘上存在数据，则加载已持久化的元数据和 FAISS 索引。"""

        if self.metadata_path.exists():
            self._metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))

        if self.index_path.exists():
            self._index = faiss.read_index(str(self.index_path))
            self._dimension = int(self._index.d)
            return

        if self._metadata:
            self._rebuild_index()
            self._persist_state()

    def _persist_state(self) -> None:
        """持久化元数据 JSON 与 FAISS 索引。"""

        self.metadata_path.write_text(json.dumps(self._metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        if self._index is None:
            if self.index_path.exists():
                self.index_path.unlink()
            return

        faiss.write_index(self._index, str(self.index_path))

    def _rebuild_index(self) -> None:
        """根据内存中的元数据重建 FAISS 索引。"""

        if not self._metadata:
            self._index = None
            self._dimension = None
            return

        vectors: np.ndarray = self._normalize_vectors([item["vector"] for item in self._metadata], enforce_dim=False)
        self._dimension = int(vectors.shape[1])
        index = faiss.IndexFlatIP(self._dimension)
        index.add(vectors)
        self._index = index

    def _normalize_vectors(
        self,
        vectors: list[list[float]],
        *,
        enforce_dim: bool = True,
    ) -> np.ndarray:
        """原地归一化向量，以便通过内积执行余弦相似度检索。"""

        matrix: np.ndarray = np.asarray(vectors, dtype="float32")
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.size == 0 or matrix.shape[1] == 0:
            raise ValueError("Vectors must contain at least one dimension.")
        if enforce_dim and self._dimension is not None and matrix.shape[1] != self._dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._dimension}, received {matrix.shape[1]}. "
                "Clear the vector store if the embedding model dimension changed."
            )

        faiss.normalize_L2(matrix)
        return matrix

    def _search_limit(self, *, limit: int, has_filter: bool) -> int:
        """在执行可选元数据过滤前，确定 FAISS 的预检索数量。"""

        total_records: int = len(self._metadata)
        if total_records == 0:
            return 0
        if has_filter:
            return total_records
        return min(total_records, max(limit * 4, limit))
