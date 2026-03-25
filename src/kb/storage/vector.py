"""基于 FAISS 的段落向量索引，附带轻量元数据映射。"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import faiss
import numpy as np


class StaleVectorIndexError(RuntimeError):
    """当存储的索引与当前嵌入模型不匹配时抛出。"""


@dataclass(slots=True)
class VectorIndexRecord:
    """与 FAISS 索引一并保存的段落元数据。"""

    paragraph_id: str
    source_id: str
    node_id: str
    text: str
    knowledge_type: str


@dataclass(slots=True)
class VectorSearchResult:
    """FAISS 检索返回的段落命中结果。"""

    paragraph_id: str
    source_id: str
    node_id: str
    text: str
    knowledge_type: str
    distance: float
    similarity: float


class VectorIndex:
    """持久化的 FAISS 索引及段落元数据映射。"""

    INDEX_FILENAME = "kb_vectors.index"
    METADATA_FILENAME = "kb_vectors.meta.json"

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir
        self.index_path = store_dir / self.INDEX_FILENAME
        self.metadata_path = store_dir / self.METADATA_FILENAME
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._index: Any | None = None
        self._dimension: int | None = None
        self._model_signature = ""
        self._metadata: list[dict[str, Any]] = []
        self._load_state()

    @property
    def model_signature(self) -> str:
        """返回当前索引绑定的嵌入模型签名。"""

        return self._model_signature

    def add_embeddings(
        self,
        *,
        model_signature: str,
        records: list[VectorIndexRecord],
        embeddings: list[list[float]],
    ) -> None:
        """写入或更新一批段落向量。"""

        if not records:
            return
        if len(records) != len(embeddings):
            raise ValueError("vector record count must match embedding count")
        if self._model_signature and self._model_signature != model_signature:
            self.reset()
        record_map: dict[str, dict[str, Any]] = {str(item["paragraph_id"]): item for item in self._metadata}
        for record, embedding in zip(records, embeddings, strict=True):
            record_map[record.paragraph_id] = {
                "paragraph_id": record.paragraph_id,
                "source_id": record.source_id,
                "node_id": record.node_id,
                "text": record.text,
                "knowledge_type": record.knowledge_type,
                "embedding": [float(value) for value in embedding],
            }
        self._model_signature = model_signature
        self._metadata = list(record_map.values())
        self._rebuild_index()
        self._persist_state()

    def search(
        self,
        *,
        model_signature: str,
        query_embedding: list[float],
        limit: int = 12,
        source_ids: list[str] | None = None,
        paragraph_ids: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        """按相似度检索段落向量。"""

        if self._model_signature and self._model_signature != model_signature:
            self.reset()
            raise StaleVectorIndexError("vector index model signature mismatch")
        if self._index is None or not self._metadata or limit <= 0:
            return []
        query_matrix = self._normalize_vectors([query_embedding])
        fetch_limit = self._search_limit(limit=limit, has_filter=bool(source_ids or paragraph_ids))
        similarities, positions = self._index.search(query_matrix, fetch_limit)
        allowed_sources = set(source_ids or [])
        allowed_paragraphs = set(paragraph_ids or [])
        results: list[VectorSearchResult] = []
        for similarity, position in zip(similarities[0].tolist(), positions[0].tolist(), strict=True):
            if position < 0 or position >= len(self._metadata):
                continue
            payload = self._metadata[position]
            if allowed_sources and str(payload["source_id"]) not in allowed_sources:
                continue
            if allowed_paragraphs and str(payload["paragraph_id"]) not in allowed_paragraphs:
                continue
            score = float(similarity)
            results.append(
                VectorSearchResult(
                    paragraph_id=str(payload["paragraph_id"]),
                    source_id=str(payload["source_id"]),
                    node_id=str(payload["node_id"]),
                    text=str(payload["text"]),
                    knowledge_type=str(payload["knowledge_type"]),
                    distance=1.0 - score,
                    similarity=score,
                )
            )
            if len(results) >= limit:
                break
        return results

    def remove_source(self, source_id: str) -> None:
        """删除指定来源关联的全部向量记录。"""

        next_metadata = [payload for payload in self._metadata if str(payload.get("source_id")) != source_id]
        if len(next_metadata) == len(self._metadata):
            return
        self._metadata = next_metadata
        self._rebuild_index()
        self._persist_state()

    def reset(self) -> None:
        """清空当前向量索引及其元数据。"""

        self._metadata = []
        self._dimension = None
        self._index = None
        self._model_signature = ""
        self._persist_state()

    def _load_state(self) -> None:
        if self.metadata_path.exists():
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._model_signature = str(payload.get("model_signature") or "")
                self._metadata = list(payload.get("records") or [])
        if self.index_path.exists():
            loaded_index: Any = faiss.read_index(str(self.index_path))
            self._index = loaded_index
            self._dimension = int(cast(Any, loaded_index).d)
            return
        if self._metadata:
            self._rebuild_index()
            self._persist_state()

    def _persist_state(self) -> None:
        payload = {
            "model_signature": self._model_signature,
            "records": self._metadata,
        }
        self.metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if self._index is None:
            if self.index_path.exists():
                self.index_path.unlink()
            return
        faiss.write_index(self._index, str(self.index_path))

    def _rebuild_index(self) -> None:
        if not self._metadata:
            self._dimension = None
            self._index = None
            return
        vectors = self._normalize_vectors(
            [list(item["embedding"]) for item in self._metadata],
            enforce_dim=False,
        )
        self._dimension = int(vectors.shape[1])
        index: Any = faiss.IndexFlatIP(self._dimension)
        index.add(vectors)
        self._index = index

    def _normalize_vectors(self, vectors: list[list[float]], *, enforce_dim: bool = True) -> np.ndarray:
        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.size == 0 or matrix.shape[1] == 0:
            raise ValueError("embedding vector must include at least one dimension")
        if enforce_dim and self._dimension is not None and matrix.shape[1] != self._dimension:
            raise ValueError("embedding vector dimension mismatch")
        faiss.normalize_L2(matrix)
        return matrix

    def _search_limit(self, *, limit: int, has_filter: bool) -> int:
        total_records = len(self._metadata)
        if total_records <= 0:
            return 0
        if has_filter:
            return total_records
        return min(total_records, max(limit * 4, limit))
