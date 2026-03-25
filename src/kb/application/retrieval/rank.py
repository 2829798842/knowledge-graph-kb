"""基于图结构的 PPR 重排器。"""

from dataclasses import dataclass, field
from time import perf_counter

import networkx as nx

from src.kb.common import (
    build_contains_edge_id,
    build_mention_edge_id,
    build_paragraph_node_id,
    build_relation_edge_id,
    build_source_node_id,
)
from src.kb.storage import AnswerReadStore
from src.utils.logger import get_logger

from .types import ParagraphHit, RetrievalLaneTrace

logger = get_logger(__name__)


@dataclass(slots=True)
class GraphRerankResult:
    """封装 PPR 重排后的命中结果与图谱高亮信息。"""

    hits: list[ParagraphHit]
    trace: RetrievalLaneTrace
    highlighted_node_ids: list[str] = field(default_factory=list)
    highlighted_edge_ids: list[str] = field(default_factory=list)


class GraphReranker:
    """在局部段落诱导子图上执行个性化 PageRank 重排。"""

    def __init__(self, *, answer_read_store: AnswerReadStore) -> None:
        self.answer_read_store = answer_read_store

    def rerank(self, hits: list[ParagraphHit], *, candidate_limit: int) -> GraphRerankResult:
        """对候选段落应用 PPR 重排并返回高亮图信息。"""

        start_time = perf_counter()
        candidate_hits = hits[: max(1, candidate_limit)]
        if len(candidate_hits) < 2:
            logger.info("PPR 重排跳过：候选段落不足，candidate_count=%s", len(candidate_hits))
            return GraphRerankResult(
                hits=hits,
                trace=self._trace(executed=False, skipped_reason="insufficient_candidates", start_time=start_time, hits=hits),
            )

        paragraph_ids = [hit.paragraph_id for hit in candidate_hits]
        paragraphs = self.answer_read_store.get_paragraphs_with_sources(paragraph_ids)
        paragraph_by_id = {str(paragraph["id"]): paragraph for paragraph in paragraphs}
        entity_links = self.answer_read_store.list_entity_links_for_paragraphs(paragraph_ids)
        relation_links = self.answer_read_store.list_relation_links_for_paragraphs(paragraph_ids)

        graph = nx.Graph()
        personalization: dict[str, float] = {}
        total_seed_score = sum(max(hit.score, 0.0) for hit in candidate_hits) or float(len(candidate_hits))

        for hit in candidate_hits:
            paragraph_node_id = build_paragraph_node_id(hit.paragraph_id)
            graph.add_node(paragraph_node_id, node_type="paragraph")
            personalization[paragraph_node_id] = max(hit.score, 0.0) / total_seed_score
            paragraph = paragraph_by_id.get(hit.paragraph_id)
            if paragraph is None:
                continue
            source_node_id = build_source_node_id(str(paragraph["source_id"]))
            graph.add_node(source_node_id, node_type="source")
            graph.add_edge(paragraph_node_id, source_node_id, weight=1.0)

        for link in entity_links:
            paragraph_node_id = build_paragraph_node_id(str(link["paragraph_id"]))
            entity_node_id = f"entity:{link['entity_id']}"
            mention_count = max(1.0, float(link.get("mention_count") or 1.0))
            graph.add_node(entity_node_id, node_type="entity")
            graph.add_edge(paragraph_node_id, entity_node_id, weight=1.0 + 0.1 * mention_count)

        for link in relation_links:
            paragraph_node_id = build_paragraph_node_id(str(link["paragraph_id"]))
            relation_node_id = f"relation:{link['relation_id']}"
            graph.add_node(relation_node_id, node_type="relation")
            graph.add_edge(paragraph_node_id, relation_node_id, weight=1.0)

        if graph.number_of_nodes() < 2 or graph.number_of_edges() == 0:
            logger.info(
                "PPR 重排跳过：局部子图过小，node_count=%s edge_count=%s",
                graph.number_of_nodes(),
                graph.number_of_edges(),
            )
            return GraphRerankResult(
                hits=hits,
                trace=self._trace(executed=False, skipped_reason="graph_empty", start_time=start_time, hits=hits),
            )

        ppr_scores = nx.pagerank(
            graph,
            alpha=0.85,
            personalization=personalization,
            weight="weight",
            max_iter=50,
        )
        reranked_hits: list[ParagraphHit] = []
        for hit in candidate_hits:
            paragraph_node_id = build_paragraph_node_id(hit.paragraph_id)
            graph_score = float(ppr_scores.get(paragraph_node_id, 0.0))
            reranked_hits.append(
                ParagraphHit(
                    paragraph_id=hit.paragraph_id,
                    source_id=hit.source_id,
                    score=round(hit.score * 0.7 + graph_score * 0.3, 6),
                    rank=hit.rank,
                    retriever="ppr",
                    match_type=hit.match_type,
                    metadata={**dict(hit.metadata), "ppr_score": graph_score, "base_score": hit.score},
                )
            )
        reranked_hits.sort(key=lambda item: (-item.score, item.paragraph_id))
        for index, hit in enumerate(reranked_hits, start=1):
            hit.rank = index
        untouched_hits = hits[len(candidate_hits) :]
        final_hits = reranked_hits + untouched_hits
        for index, hit in enumerate(final_hits, start=1):
            hit.rank = index

        top_ids = {hit.paragraph_id for hit in reranked_hits[:6]}
        highlighted_node_ids: list[str] = []
        highlighted_edge_ids: list[str] = []
        for paragraph_id in top_ids:
            paragraph = paragraph_by_id.get(paragraph_id)
            if paragraph is None:
                continue
            source_id = str(paragraph["source_id"])
            highlighted_node_ids.extend([build_source_node_id(source_id), build_paragraph_node_id(paragraph_id)])
            highlighted_edge_ids.append(build_contains_edge_id(source_id, paragraph_id))
        for link in entity_links:
            paragraph_id = str(link["paragraph_id"])
            if paragraph_id not in top_ids:
                continue
            highlighted_node_ids.append(f"entity:{link['entity_id']}")
            highlighted_edge_ids.append(build_mention_edge_id(paragraph_id, str(link["entity_id"])))
        for link in relation_links:
            paragraph_id = str(link["paragraph_id"])
            if paragraph_id not in top_ids:
                continue
            highlighted_edge_ids.append(build_relation_edge_id(str(link["relation_id"])))

        result = GraphRerankResult(
            hits=final_hits,
            trace=self._trace(executed=True, skipped_reason=None, start_time=start_time, hits=final_hits),
            highlighted_node_ids=self._deduplicate(highlighted_node_ids),
            highlighted_edge_ids=self._deduplicate(highlighted_edge_ids),
        )
        logger.info(
            "PPR 重排完成：candidate_count=%s reranked_count=%s highlighted_node_count=%s highlighted_edge_count=%s latency_ms=%s",
            len(candidate_hits),
            len(result.hits),
            len(result.highlighted_node_ids),
            len(result.highlighted_edge_ids),
            result.trace.latency_ms,
        )
        return result

    def _trace(
        self,
        *,
        executed: bool,
        skipped_reason: str | None,
        start_time: float,
        hits: list[ParagraphHit],
    ) -> RetrievalLaneTrace:
        """构造 PPR 重排链路的执行轨迹。"""

        return RetrievalLaneTrace(
            executed=executed,
            skipped_reason=skipped_reason,
            hit_count=len(hits),
            latency_ms=round((perf_counter() - start_time) * 1000.0, 2),
            top_paragraph_ids=[hit.paragraph_id for hit in hits[:6]],
        )

    def _deduplicate(self, values: list[str]) -> list[str]:
        """按首次出现顺序去重高亮节点或边。"""

        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
