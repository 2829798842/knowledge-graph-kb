"""模块名称：services.query_service

主要功能：执行向量召回、个性化 PageRank 重排并生成最终问答结果。
"""

from collections import deque

import networkx as nx
from sqlmodel import Session, select

from kb_graph.config import Settings
from kb_graph.contracts.api.graph_contracts import GraphEdgeRead, GraphNodeRead
from kb_graph.contracts.api.query_contracts import CitationRead, QueryResponse
from kb_graph.data.models import Chunk, EdgeType, GraphEdge, GraphNode, NodeType
from kb_graph.services.graph_service import build_graph_response, to_graph_edge_read
from kb_graph.services.openai_service import OpenAiService
from kb_graph.services.vector_store_service import LanceDbVectorStore

PAGE_RANK_ALPHA: float = 0.85
SUBGRAPH_EXPANSION_DEPTH: int = 2
MIN_NODE_WEIGHT: float = 0.001
MIN_EDGE_WEIGHT: float = 0.01


class QueryService:
    """问答检索服务。

    Attributes:
        settings (Settings): 当前应用配置。
        openai_service (OpenAiService): OpenAI 服务。
        vector_store (LanceDbVectorStore): 向量存储服务。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        openai_service: OpenAiService,
        vector_store: LanceDbVectorStore,
    ) -> None:
        """初始化问答检索服务。

        Args:
            settings: 当前应用配置。
            openai_service: OpenAI 服务。
            vector_store: 向量存储服务。
        """

        self.settings: Settings = settings
        self.openai_service: OpenAiService = openai_service
        self.vector_store: LanceDbVectorStore = vector_store

    def answer(
        self,
        session: Session,
        *,
        query: str,
        document_ids: list[str] | None = None,
        top_k: int = 6,
    ) -> QueryResponse:
        """执行问答检索并返回排序结果。

        Args:
            session: 数据库会话。
            query: 用户问题。
            document_ids: 可选的文档过滤范围。
            top_k: 用于最终回答的上下文块数量。

        Returns:
            QueryResponse: 最终问答结果。
        """

        query_embedding: list[float] = self.openai_service.embed_texts([query])[0]
        seed_results = self.vector_store.search(
            query_embedding,
            limit=self.settings.query_seed_limit,
            document_ids=document_ids,
        )
        if not seed_results:
            return QueryResponse(answer="No indexed chunks matched the query yet.", citations=[], ranked_nodes=[], ranked_edges=[])

        graph_nodes: list[GraphNode] = session.exec(select(GraphNode)).all()
        graph_edges: list[GraphEdge] = session.exec(select(GraphEdge)).all()
        graph = self._build_graph(graph_nodes, graph_edges)
        subgraph = self._seeded_subgraph(graph, [result.node_id for result in seed_results], depth=SUBGRAPH_EXPANSION_DEPTH)

        personalization: dict[str, float] = {
            result.node_id: max(result.similarity, MIN_NODE_WEIGHT)
            for result in seed_results
            if result.node_id in subgraph.nodes
        }
        if not personalization:
            personalization = {node_id: 1.0 for node_id in list(subgraph.nodes)[:1]}

        ranking: dict[str, float] = self._personalized_pagerank(
            subgraph,
            personalization=personalization,
            alpha=PAGE_RANK_ALPHA,
        )
        ranked_nodes: list[tuple[str, float]] = sorted(ranking.items(), key=lambda item: item[1], reverse=True)
        graph_snapshot = build_graph_response(
            session,
            document_id=document_ids[0] if document_ids and len(document_ids) == 1 else None,
            include_chunks=True,
            ranked_scores=ranking,
        )

        candidate_chunk_node_ids: list[str] = [node_id for node_id, _score in ranked_nodes if node_id.startswith("chunk:")]
        if not candidate_chunk_node_ids:
            candidate_chunk_node_ids = [result.node_id for result in seed_results]

        selected_chunk_node_ids: list[str] = candidate_chunk_node_ids[
            : max(1, min(top_k, self.settings.query_context_chunks))
        ]
        chunk_rows: list[Chunk] = session.exec(select(Chunk).where(Chunk.node_id.in_(selected_chunk_node_ids))).all()
        chunk_map: dict[str, Chunk] = {chunk.node_id: chunk for chunk in chunk_rows}

        citations: list[CitationRead] = []
        context_blocks: list[dict[str, str]] = []
        for node_id in selected_chunk_node_ids:
            chunk = chunk_map.get(node_id)
            if chunk is None:
                continue
            score: float = ranking.get(node_id, 0.0)
            document_name: str = self._document_name(session, chunk.document_id)
            excerpt: str = chunk.text[:500]
            citations.append(
                CitationRead(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    node_id=node_id,
                    document_name=document_name,
                    excerpt=excerpt,
                    score=score,
                )
            )
            context_blocks.append(
                {
                    "chunk_id": chunk.id,
                    "document_name": document_name,
                    "excerpt": excerpt,
                }
            )

        answer_text: str = "No indexed chunks matched the query yet."
        if context_blocks:
            answer_text = self.openai_service.answer_query(query, context_blocks)

        ranked_edge_payload: list[GraphEdgeRead] = self._ranked_edges(graph_edges, ranking)
        ranked_node_payload: list[GraphNodeRead] = self._ranked_nodes(graph_snapshot.nodes, ranking)
        return QueryResponse(
            answer=answer_text,
            citations=citations,
            ranked_nodes=ranked_node_payload,
            ranked_edges=ranked_edge_payload,
        )

    def _build_graph(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> nx.DiGraph:
        """构建用于排序的有向图。

        Args:
            nodes: 图节点列表。
            edges: 图边列表。

        Returns:
            nx.DiGraph: 构建完成的有向图。
        """

        graph = nx.DiGraph()
        for node in nodes:
            graph.add_node(node.id, type=node.node_type, label=node.label, metadata=node.metadata_json)
        for edge in edges:
            weight: float = max(edge.weight, MIN_EDGE_WEIGHT)
            graph.add_edge(edge.source_node_id, edge.target_node_id, weight=weight, type=edge.edge_type)
            if edge.edge_type in {EdgeType.SEMANTIC, EdgeType.MANUAL, EdgeType.MENTIONS}:
                graph.add_edge(edge.target_node_id, edge.source_node_id, weight=weight, type=edge.edge_type)
        return graph

    def _seeded_subgraph(self, graph: nx.DiGraph, seed_nodes: list[str], depth: int) -> nx.DiGraph:
        """从种子节点扩展出局部子图。

        Args:
            graph: 全量图。
            seed_nodes: 种子节点列表。
            depth: 扩展深度。

        Returns:
            nx.DiGraph: 截取后的局部子图。
        """

        visited: set[str] = set(seed_nodes)
        queue: deque[tuple[str, int]] = deque((node_id, 0) for node_id in seed_nodes if node_id in graph)
        while queue:
            node_id, level = queue.popleft()
            if level >= depth:
                continue
            neighbors: set[str] = set(graph.successors(node_id)).union(set(graph.predecessors(node_id)))
            for neighbor in neighbors:
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, level + 1))
        return graph.subgraph(visited).copy()

    def _personalized_pagerank(
        self,
        graph: nx.DiGraph,
        *,
        personalization: dict[str, float],
        alpha: float,
        max_iter: int = 100,
        tol: float = 1e-6,
    ) -> dict[str, float]:
        """执行带个性化向量的 PageRank。

        Args:
            graph: 参与排序的子图。
            personalization: 个性化初始权重。
            alpha: 阻尼系数。
            max_iter: 最大迭代次数。
            tol: 收敛阈值。

        Returns:
            dict[str, float]: 节点得分映射。
        """

        node_ids: list[str] = list(graph.nodes)
        if not node_ids:
            return {}

        weights: dict[str, float] = {node_id: max(personalization.get(node_id, 0.0), 0.0) for node_id in node_ids}
        total_weight: float = sum(weights.values())
        if total_weight == 0:
            weights = {node_id: 1.0 / len(node_ids) for node_id in node_ids}
        else:
            weights = {node_id: weight / total_weight for node_id, weight in weights.items()}

        ranks: dict[str, float] = weights.copy()
        out_weights: dict[str, float] = {
            node_id: sum(max(data.get("weight", 1.0), 0.0) for _, _, data in graph.out_edges(node_id, data=True))
            for node_id in node_ids
        }

        for _ in range(max_iter):
            next_ranks: dict[str, float] = {node_id: (1.0 - alpha) * weights[node_id] for node_id in node_ids}
            # 悬挂节点没有出边，需要将其质量按个性化权重重新分配。
            dangling_mass: float = sum(ranks[node_id] for node_id in node_ids if out_weights[node_id] == 0)

            for node_id in node_ids:
                total_out_weight: float = out_weights[node_id]
                if total_out_weight == 0:
                    continue
                for _, target_node_id, data in graph.out_edges(node_id, data=True):
                    edge_weight: float = max(data.get("weight", 1.0), 0.0)
                    if edge_weight == 0:
                        continue
                    next_ranks[target_node_id] += alpha * ranks[node_id] * (edge_weight / total_out_weight)

            if dangling_mass:
                for node_id in node_ids:
                    next_ranks[node_id] += alpha * dangling_mass * weights[node_id]

            delta: float = sum(abs(next_ranks[node_id] - ranks[node_id]) for node_id in node_ids)
            ranks = next_ranks
            if delta < tol:
                break

        normalized_total: float = sum(ranks.values())
        if normalized_total == 0:
            return {node_id: 0.0 for node_id in node_ids}
        return {node_id: score / normalized_total for node_id, score in ranks.items()}

    def _document_name(self, session: Session, document_id: str) -> str:
        """获取文档展示名称。

        Args:
            session: 数据库会话。
            document_id: 文档主键。

        Returns:
            str: 文档展示名称；找不到时返回原始主键。
        """

        document_node = session.exec(
            select(GraphNode).where(
                GraphNode.ref_id == document_id,
                GraphNode.node_type == NodeType.DOCUMENT,
            )
        ).first()
        if document_node is not None:
            return document_node.label
        return document_id

    def _ranked_nodes(self, nodes: list[GraphNodeRead], ranking: dict[str, float]) -> list[GraphNodeRead]:
        """对图节点响应结果按得分排序。

        Args:
            nodes: 原始节点响应列表。
            ranking: 节点得分映射。

        Returns:
            list[GraphNodeRead]: 已排序节点列表。
        """

        scored_nodes: list[GraphNodeRead] = [
            GraphNodeRead(**{**node.model_dump(), "score": ranking.get(node.id, node.score)})
            for node in nodes
        ]
        return sorted(scored_nodes, key=lambda node: node.score or 0.0, reverse=True)[:20]

    def _ranked_edges(self, edges: list[GraphEdge], ranking: dict[str, float]) -> list[GraphEdgeRead]:
        """对图边响应结果按综合分数排序。

        Args:
            edges: 原始图边列表。
            ranking: 节点得分映射。

        Returns:
            list[GraphEdgeRead]: 已排序图边列表。
        """

        scored_edges: list[tuple[float, GraphEdgeRead]] = []
        for edge in edges:
            combined_score: float = ranking.get(edge.source_node_id, 0.0) + ranking.get(edge.target_node_id, 0.0) + edge.weight
            payload = to_graph_edge_read(edge)
            payload.metadata = {**payload.metadata, "rank_score": combined_score}
            scored_edges.append((combined_score, payload))
        scored_edges.sort(key=lambda item: item[0], reverse=True)
        return [edge for _, edge in scored_edges[:20]]
