"""模块名称：contracts.api.query_contracts

主要功能：定义问答检索请求、引用信息与排序结果契约。
"""

from pydantic import BaseModel

from src.schemas.api.graph_contracts import GraphEdgeRead, GraphNodeRead


class QueryRequest(BaseModel):
    """问答查询请求模型。

    Attributes:
        query (str): 用户输入问题。
        document_ids (list[str] | None): 可选的文档过滤范围。
        top_k (int): 参与最终回答的上下文块数量。
    """

    query: str
    document_ids: list[str] | None = None
    top_k: int = 6


class CitationRead(BaseModel):
    """引用片段模型。

    Attributes:
        chunk_id (str): 切块主键。
        document_id (str): 文档主键。
        node_id (str): 图节点标识。
        document_name (str): 文档展示名称。
        excerpt (str): 引用片段。
        score (float): 排序得分。
    """

    chunk_id: str
    document_id: str
    node_id: str
    document_name: str
    excerpt: str
    score: float


class QueryResponse(BaseModel):
    """问答查询响应模型。

    Attributes:
        answer (str): 最终回答文本。
        citations (list[CitationRead]): 引用片段列表。
        ranked_nodes (list[GraphNodeRead]): 高亮节点排序结果。
        ranked_edges (list[GraphEdgeRead]): 高亮边排序结果。
    """

    answer: str
    citations: list[CitationRead]
    ranked_nodes: list[GraphNodeRead]
    ranked_edges: list[GraphEdgeRead]
