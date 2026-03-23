"""模块名称：tests.test_query_service

主要功能：验证查询服务会将手工边纳入个性化 PageRank 排序结果。
"""

from src.config import Settings
from src.data import Chunk, GraphEdge, GraphNode, NodeType
from src.services import QueryService, VectorSearchResult


class FakeOpenAiService:
    """用于测试的 OpenAI 服务替身。"""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """返回固定的二维向量结果。

        Args:
            texts: 待嵌入的文本列表。

        Returns:
            list[list[float]]: 固定的嵌入向量列表。
        """

        return [[1.0, 0.0] for _ in texts]

    def answer_query(self, query: str, context_blocks: list[dict[str, str]]) -> str:
        """拼接引用块标识，模拟最终回答。

        Args:
            query: 用户问题。
            context_blocks: 用于回答的上下文块。

        Returns:
            str: 包含引用块标识的模拟回答文本。
        """

        citation_ids = ", ".join(block["chunk_id"] for block in context_blocks)
        return f"Answer based on {citation_ids}"


class FakeVectorStore:
    """用于测试的向量存储替身。"""

    def search(self, query_vector: list[float], limit: int = 20, document_ids: list[str] | None = None):
        """返回固定的召回结果。

        Args:
            query_vector: 查询向量。
            limit: 期望返回的结果上限。
            document_ids: 可选的文档过滤条件。

        Returns:
            list[VectorSearchResult]: 固定的向量召回结果。
        """

        return [
            VectorSearchResult(
                chunk_id="chunk-a-id",
                document_id="doc-1",
                node_id="chunk:a",
                text="first chunk",
                distance=0.1,
                similarity=0.9,
                vector=[1.0, 0.0],
            )
        ]


def test_query_service_uses_manual_edges_in_ranking(session):
    """验证手工边会影响排序结果和最终返回的高亮边。"""

    session.add(
        GraphNode(
            id="document:doc-1",
            node_type=NodeType.DOCUMENT,
            label="Doc One",
            ref_id="doc-1",
            metadata_json={},
        )
    )
    session.add(GraphNode(id="chunk:a", node_type=NodeType.CHUNK, label="Chunk A", ref_id="chunk-a-id", metadata_json={}))
    session.add(GraphNode(id="chunk:b", node_type=NodeType.CHUNK, label="Chunk B", ref_id="chunk-b-id", metadata_json={}))
    session.add(GraphNode(id="entity:topic", node_type=NodeType.ENTITY, label="Topic", ref_id="entity:topic", metadata_json={}))
    session.add(Chunk(id="chunk-a-id", document_id="doc-1", node_id="chunk:a", chunk_index=0, token_count=4, text="Chunk A context"))
    session.add(Chunk(id="chunk-b-id", document_id="doc-1", node_id="chunk:b", chunk_index=1, token_count=4, text="Chunk B context"))
    session.add(GraphEdge(source_node_id="document:doc-1", target_node_id="chunk:a", edge_type="contains", weight=1.0, metadata_json={}))
    session.add(GraphEdge(source_node_id="document:doc-1", target_node_id="chunk:b", edge_type="contains", weight=1.0, metadata_json={}))
    session.add(GraphEdge(source_node_id="chunk:a", target_node_id="entity:topic", edge_type="mentions", weight=1.0, metadata_json={}))
    session.add(GraphEdge(source_node_id="entity:topic", target_node_id="chunk:b", edge_type="manual", weight=1.8, metadata_json={}))
    session.commit()

    service = QueryService(
        settings=Settings(openai_api_key="test-key"),
        openai_service=FakeOpenAiService(),
        vector_store=FakeVectorStore(),
    )

    result = service.answer(session, query="How is chunk B related?", document_ids=["doc-1"], top_k=2)

    ranked_node_ids = [node.id for node in result.ranked_nodes]
    assert "chunk:b" in ranked_node_ids
    assert any(edge.type == "manual" for edge in result.ranked_edges)
    assert len(result.citations) == 2
    assert "chunk-a-id" in result.answer
