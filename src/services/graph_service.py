"""模块名称：services.graph_service

主要功能：提供图节点与图边维护、语义连边构建以及图谱响应组装能力。
"""

import re
from typing import Any, Iterable

import numpy as np
from sqlmodel import Session, select

from src.data import (
    Chunk,
    Document,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    document_node_id,
    entity_node_id,
    normalize_entity_name,
)
from src.schemas import ExtractionResult
from src.schemas.api import GraphEdgeRead, GraphNodeRead, GraphResponse
from src.services.vector_store_service import FaissVectorStore, VectorRecord

SIMILAR_RECORD_LIMIT: int = 6
GRAPH_EDGE_LIMIT_MULTIPLIER: int = 2


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算两个向量的余弦相似度。

    Args:
        left: 左侧向量。
        right: 右侧向量。

    Returns:
        float: 余弦相似度。
    """

    left_array = np.array(left, dtype=np.float32)
    right_array = np.array(right, dtype=np.float32)
    denominator: float = float(np.linalg.norm(left_array) * np.linalg.norm(right_array))
    if denominator == 0:
        return 0.0
    return float(np.dot(left_array, right_array) / denominator)


def chunk_mentions_entity(chunk_text: str, entity_name: str) -> bool:
    """判断切块文本是否真正提及某个实体。

    Args:
        chunk_text: 切块文本。
        entity_name: 实体名称。

    Returns:
        bool: 当切块文本命中实体时返回 `True`。
    """

    normalized_chunk_text: str = normalize_entity_name(chunk_text)
    normalized_entity_name: str = normalize_entity_name(entity_name)
    if not normalized_chunk_text or not normalized_entity_name:
        return False

    # 使用词边界与空白折叠匹配，避免短实体名称误命中更长单词内部子串。
    escaped_tokens: list[str] = [re.escape(token) for token in normalized_entity_name.split()]
    pattern: str = r"(?<![a-z0-9_])" + r"\s+".join(escaped_tokens) + r"(?![a-z0-9_])"
    return re.search(pattern, normalized_chunk_text, re.IGNORECASE) is not None


def ensure_graph_node(
    session: Session,
    *,
    node_id: str,
    node_type: NodeType,
    label: str,
    ref_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> GraphNode:
    """确保图节点存在，不存在则创建。

    Args:
        session: 数据库会话。
        node_id: 节点标识。
        node_type: 节点类型。
        label: 节点展示名称。
        ref_id: 关联业务标识。
        metadata: 节点扩展信息。

    Returns:
        GraphNode: 创建或更新后的图节点。
    """

    node = session.get(GraphNode, node_id)
    if node is None:
        node = GraphNode(
            id=node_id,
            node_type=node_type,
            label=label,
            ref_id=ref_id,
            metadata_json=metadata or {},
        )
        session.add(node)
        session.flush()
        return node

    node.label = label
    node.ref_id = ref_id
    node.metadata_json = {**node.metadata_json, **(metadata or {})}
    session.add(node)
    session.flush()
    return node


def ensure_graph_edge(
    session: Session,
    *,
    source_node_id: str,
    target_node_id: str,
    edge_type: EdgeType,
    weight: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> GraphEdge:
    """确保图边存在，不存在则创建。

    Args:
        session: 数据库会话。
        source_node_id: 源节点标识。
        target_node_id: 目标节点标识。
        edge_type: 边类型。
        weight: 边权重。
        metadata: 边扩展信息。

    Returns:
        GraphEdge: 创建或更新后的图边。
    """

    existing_edges: list[GraphEdge] = list(session.exec(select(GraphEdge)).all())
    edge = next(
        (
            existing_edge
            for existing_edge in existing_edges
            if existing_edge.source_node_id == source_node_id
            and existing_edge.target_node_id == target_node_id
            and existing_edge.edge_type == edge_type
        ),
        None,
    )
    if edge is None:
        edge = GraphEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            weight=weight,
            metadata_json=metadata or {},
        )
        session.add(edge)
        session.flush()
        return edge

    edge.weight = weight
    edge.metadata_json = {**edge.metadata_json, **(metadata or {})}
    session.add(edge)
    session.flush()
    return edge


def seed_document_node(session: Session, document: Document) -> GraphNode:
    """为文档建立图节点。

    Args:
        session: 数据库会话。
        document: 文档模型。

    Returns:
        GraphNode: 对应的文档图节点。
    """

    return ensure_graph_node(
        session,
        node_id=document_node_id(document.id),
        node_type=NodeType.DOCUMENT,
        label=document.original_name,
        ref_id=document.id,
        metadata={"file_type": document.file_type, **document.metadata_json},
    )


def create_chunk_graph(
    session: Session,
    *,
    document: Document,
    chunks: list[Chunk],
) -> None:
    """为文档切块建立包含关系图。

    Args:
        session: 数据库会话。
        document: 文档模型。
        chunks: 文档切块列表。
    """

    document_node_key: str = document_node_id(document.id)
    for chunk in chunks:
        ensure_graph_node(
            session,
            node_id=chunk.node_id,
            node_type=NodeType.CHUNK,
            label=f"{document.original_name} #{chunk.chunk_index + 1}",
            ref_id=chunk.id,
            metadata={"document_id": document.id, "chunk_index": chunk.chunk_index},
        )
        ensure_graph_edge(
            session,
            source_node_id=document_node_key,
            target_node_id=chunk.node_id,
            edge_type=EdgeType.CONTAINS,
            weight=1.0,
            metadata={"document_id": document.id},
        )


def create_entity_graph(
    session: Session,
    *,
    document: Document,
    chunks: list[Chunk],
    extraction: ExtractionResult,
) -> None:
    """根据抽取结果建立实体与提及关系。

    Args:
        session: 数据库会话。
        document: 文档模型。
        chunks: 文档切块列表。
        extraction: 实体关系抽取结果。
    """

    document_node_key: str = document_node_id(document.id)
    for entity in extraction.entities:
        normalized_name: str = normalize_entity_name(entity.name)
        if not normalized_name:
            continue
        entity_node_key: str = entity_node_id(entity.name)
        ensure_graph_node(
            session,
            node_id=entity_node_key,
            node_type=NodeType.ENTITY,
            label=entity.name.strip(),
            ref_id=entity_node_key,
            metadata={"description": entity.description},
        )

        is_linked: bool = False
        for chunk in chunks:
            if chunk_mentions_entity(chunk.text, entity.name):
                ensure_graph_edge(
                    session,
                    source_node_id=chunk.node_id,
                    target_node_id=entity_node_key,
                    edge_type=EdgeType.MENTIONS,
                    weight=1.0,
                    metadata={"document_id": document.id},
                )
                is_linked = True

        if not is_linked:
            ensure_graph_edge(
                session,
                source_node_id=document_node_key,
                target_node_id=entity_node_key,
                edge_type=EdgeType.MENTIONS,
                weight=1.0,
                metadata={"document_id": document.id, "source": "llm_extraction"},
            )

    for relation in extraction.relations:
        if not relation.source or not relation.target:
            continue
        source_entity_key: str = entity_node_id(relation.source)
        target_entity_key: str = entity_node_id(relation.target)
        ensure_graph_node(
            session,
            node_id=source_entity_key,
            node_type=NodeType.ENTITY,
            label=relation.source,
            ref_id=source_entity_key,
            metadata={},
        )
        ensure_graph_node(
            session,
            node_id=target_entity_key,
            node_type=NodeType.ENTITY,
            label=relation.target,
            ref_id=target_entity_key,
            metadata={},
        )
        ensure_graph_edge(
            session,
            source_node_id=source_entity_key,
            target_node_id=target_entity_key,
            edge_type=EdgeType.MENTIONS,
            weight=max(0.5, relation.weight),
            metadata={"relation": relation.relation, "document_id": document.id},
        )


def create_semantic_edges(
    session: Session,
    *,
    vector_store: FaissVectorStore,
    chunk_vectors: list[VectorRecord],
    threshold: float,
) -> None:
    """根据嵌入相似度建立语义边。

    Args:
        session: 数据库会话。
        vector_store: 向量存储服务。
        chunk_vectors: 当前文档切块向量列表。
        threshold: 建立语义边的最小相似度阈值。
    """

    for record in chunk_vectors:
        similar_records = vector_store.search(record.vector, limit=SIMILAR_RECORD_LIMIT)
        for similar in similar_records:
            if similar.node_id == record.node_id:
                continue
            similarity: float = cosine_similarity(record.vector, similar.vector)
            if similarity < threshold:
                continue
            source_node_id, target_node_id = sorted([record.node_id, similar.node_id])
            ensure_graph_edge(
                session,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                edge_type=EdgeType.SEMANTIC,
                weight=similarity,
                metadata={"distance": similar.distance},
            )


def build_graph_response(
    session: Session,
    *,
    document_id: str | None = None,
    include_chunks: bool = True,
    limit: int = 300,
    ranked_scores: dict[str, float] | None = None,
) -> GraphResponse:
    """组装前端所需的图谱响应。

    Args:
        session: 数据库会话。
        document_id: 可选的文档过滤条件。
        include_chunks: 是否返回切块节点。
        limit: 节点返回上限。
        ranked_scores: 可选的排序得分映射。

    Returns:
        GraphResponse: 序列化后的图谱响应。
    """

    active_scores: dict[str, float] = ranked_scores or {}
    all_nodes: list[GraphNode] = list(session.exec(select(GraphNode)).all())
    all_edges: list[GraphEdge] = list(session.exec(select(GraphEdge)).all())
    if document_id:
        base_node_ids: set[str] = {document_node_id(document_id)}
        document_chunks: list[Chunk] = list(session.exec(select(Chunk).where(Chunk.document_id == document_id)).all())
        base_node_ids.update(chunk.node_id for chunk in document_chunks)

        related_edges: list[GraphEdge] = [
            edge
            for edge in all_edges
            if edge.source_node_id in base_node_ids or edge.target_node_id in base_node_ids
        ]
        node_ids: set[str] = set(base_node_ids)
        for edge in related_edges:
            node_ids.add(edge.source_node_id)
            node_ids.add(edge.target_node_id)
        nodes: list[GraphNode] = [node for node in all_nodes if node.id in node_ids]
        edges: list[GraphEdge] = [
            edge
            for edge in all_edges
            if edge.source_node_id in node_ids and edge.target_node_id in node_ids
        ]
    else:
        nodes = all_nodes
        edges = all_edges

    if not include_chunks:
        chunk_ids: set[str] = {node.id for node in nodes if node.node_type == NodeType.CHUNK}
        nodes = [node for node in nodes if node.id not in chunk_ids]
        edges = [edge for edge in edges if edge.source_node_id not in chunk_ids and edge.target_node_id not in chunk_ids]

    visible_nodes: list[GraphNode] = nodes[:limit]
    visible_node_ids: set[str] = {node.id for node in visible_nodes}
    visible_edges: list[GraphEdge] = [
        edge
        for edge in edges
        if edge.source_node_id in visible_node_ids and edge.target_node_id in visible_node_ids
    ][: limit * GRAPH_EDGE_LIMIT_MULTIPLIER]

    node_payload: list[GraphNodeRead] = [
        GraphNodeRead(
            id=node.id,
            type=node.node_type,
            label=node.label,
            score=active_scores.get(node.id),
            metadata=node.metadata_json,
        )
        for node in visible_nodes
    ]
    edge_payload: list[GraphEdgeRead] = [to_graph_edge_read(edge) for edge in visible_edges]
    return GraphResponse(nodes=node_payload, edges=edge_payload)


def to_graph_edge_read(edge: GraphEdge) -> GraphEdgeRead:
    """将数据库图边模型转换为响应模型。

    Args:
        edge: 数据库图边模型。

    Returns:
        GraphEdgeRead: 序列化后的图边响应模型。
    """

    return GraphEdgeRead(
        id=edge.id,
        source=edge.source_node_id,
        target=edge.target_node_id,
        type=edge.edge_type,
        weight=edge.weight,
        metadata=edge.metadata_json,
    )


def fetch_nodes_by_ids(session: Session, node_ids: Iterable[str]) -> list[GraphNode]:
    """按节点标识批量查询图节点。

    Args:
        session: 数据库会话。
        node_ids: 节点标识集合。

    Returns:
        list[GraphNode]: 命中的节点列表。
    """

    node_list: list[str] = list(node_ids)
    if not node_list:
        return []
    node_id_set: set[str] = set(node_list)
    all_nodes: list[GraphNode] = list(session.exec(select(GraphNode)).all())
    return [node for node in all_nodes if node.id in node_id_set]
