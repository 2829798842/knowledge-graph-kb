"""模块名称：services.vector_store_service

主要功能：封装 LanceDB 向量写入与按余弦距离检索的能力。
"""

from typing import Any

import lancedb

from kb_graph.config import Settings, ensure_app_dirs


class VectorRecord:
    """向量写入记录。

    Attributes:
        chunk_id (str): 切块主键。
        document_id (str): 文档主键。
        node_id (str): 图节点标识。
        text (str): 切块文本。
        vector (list[float]): 嵌入向量。
    """

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        node_id: str,
        text: str,
        vector: list[float],
    ) -> None:
        """初始化向量写入记录。

        Args:
            chunk_id: 切块主键。
            document_id: 文档主键。
            node_id: 图节点标识。
            text: 切块文本。
            vector: 嵌入向量。
        """

        self.chunk_id: str = chunk_id
        self.document_id: str = document_id
        self.node_id: str = node_id
        self.text: str = text
        self.vector: list[float] = vector


class VectorSearchResult:
    """向量检索结果。

    Attributes:
        chunk_id (str): 切块主键。
        document_id (str): 文档主键。
        node_id (str): 图节点标识。
        text (str): 切块文本。
        distance (float): 向量距离。
        similarity (float): 由距离换算的相似度。
        vector (list[float]): 命中结果对应向量。
    """

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
        """初始化向量检索结果。

        Args:
            chunk_id: 切块主键。
            document_id: 文档主键。
            node_id: 图节点标识。
            text: 切块文本。
            distance: 向量距离。
            similarity: 相似度分数。
            vector: 命中向量。
        """

        self.chunk_id: str = chunk_id
        self.document_id: str = document_id
        self.node_id: str = node_id
        self.text: str = text
        self.distance: float = distance
        self.similarity: float = similarity
        self.vector: list[float] = vector


class LanceDbVectorStore:
    """LanceDB 向量存储服务。

    Attributes:
        TABLE_NAME (str): 向量表名。
        settings (Settings): 当前应用配置。
        db (Any): LanceDB 数据库连接。
    """

    TABLE_NAME: str = "chunk_embeddings"

    def __init__(self, settings: Settings) -> None:
        """初始化 LanceDB 向量存储。

        Args:
            settings: 当前应用配置。
        """

        self.settings: Settings = settings
        ensure_app_dirs(settings)
        self.db: Any = lancedb.connect(str(settings.resolved_lancedb_path))

    def add_embeddings(self, records: list[VectorRecord]) -> None:
        """批量写入嵌入向量。

        Args:
            records: 待写入的向量记录列表。
        """

        if not records:
            return

        payload: list[dict[str, Any]] = [
            {
                "chunk_id": record.chunk_id,
                "document_id": record.document_id,
                "node_id": record.node_id,
                "text": record.text,
                "vector": record.vector,
            }
            for record in records
        ]
        if self.TABLE_NAME in self.db.table_names():
            table = self.db.open_table(self.TABLE_NAME)
            table.add(payload)
            return
        self.db.create_table(self.TABLE_NAME, data=payload, mode="overwrite")

    def search(
        self,
        query_vector: list[float],
        limit: int = 20,
        document_ids: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        """执行向量检索并返回过滤后的命中结果。

        Args:
            query_vector: 查询向量。
            limit: 需要返回的命中数量。
            document_ids: 可选的文档范围过滤条件。

        Returns:
            list[VectorSearchResult]: 过滤后的向量命中列表。
        """

        if self.TABLE_NAME not in self.db.table_names():
            return []

        table = self.db.open_table(self.TABLE_NAME)
        search = table.search(query_vector)
        if hasattr(search, "metric"):
            search = search.metric("cosine")
        rows: list[dict[str, Any]] = search.limit(max(limit * 4, limit)).to_list()

        filtered_results: list[VectorSearchResult] = []
        allowed_documents: set[str] = set(document_ids or [])
        for row in rows:
            if allowed_documents and row["document_id"] not in allowed_documents:
                continue
            distance: float = float(row.get("_distance", 0.0))
            similarity: float = max(0.0, 1.0 - distance)
            filtered_results.append(
                VectorSearchResult(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    node_id=row["node_id"],
                    text=row["text"],
                    distance=distance,
                    similarity=similarity,
                    vector=[float(value) for value in row["vector"]],
                )
            )
            if len(filtered_results) >= limit:
                break
        return filtered_results
