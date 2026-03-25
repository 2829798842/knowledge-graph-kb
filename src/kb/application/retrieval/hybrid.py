"""统一编排结构化、向量与 PPR 重排的双路检索器。"""

from time import perf_counter

from src.config import Settings
from src.kb.storage import RecordStore, StaleVectorIndexError
from src.utils.logger import get_logger

from .rank import GraphReranker
from .structured import StructuredParagraphRetriever
from .types import HybridRetrievalResult, ParagraphHit, RetrievalLaneTrace, RetrievalRequest, RetrievalTrace
from .vector import VectorParagraphRetriever

EXACT_MATCH_TYPES: set[str] = {"record_key_exact", "cell_exact"}
logger = get_logger(__name__)


class HybridAnswerRetriever:
    """优先执行结构化检索，再按需补充向量检索与图重排。"""

    def __init__(
        self,
        *,
        settings: Settings,
        record_store: RecordStore,
        structured_retriever: StructuredParagraphRetriever,
        vector_retriever: VectorParagraphRetriever,
        graph_reranker: GraphReranker,
    ) -> None:
        self.settings = settings
        self.record_store = record_store
        self.structured_retriever = structured_retriever
        self.vector_retriever = vector_retriever
        self.graph_reranker = graph_reranker

    def retrieve(self, request: RetrievalRequest) -> HybridRetrievalResult:
        """执行双路检索并返回最终命中、检索模式与轨迹。"""

        total_start = perf_counter()
        candidate_paragraph_ids = self._resolve_candidate_paragraph_ids(request)
        structured_hits, structured_trace = self.structured_retriever.retrieve(request)
        vector_trace = self._skip_trace("not_requested")
        fusion_trace = self._skip_trace("not_requested")
        ppr_trace = self._skip_trace("disabled")

        if request.worksheet_names and candidate_paragraph_ids == []:
            trace = RetrievalTrace(
                structured=structured_trace,
                vector=self._skip_trace("worksheet_scope_empty"),
                fusion=self._skip_trace("worksheet_scope_empty"),
                ppr=self._skip_trace("worksheet_scope_empty"),
                total_ms=round((perf_counter() - total_start) * 1000.0, 2),
            )
            logger.info("双路检索结束：工作表过滤后没有候选段落，worksheet_count=%s", len(request.worksheet_names))
            return HybridRetrievalResult(hits=[], retrieval_mode="none", trace=trace)

        short_circuit_hits = self._short_circuit_hits(request, structured_hits)
        if short_circuit_hits:
            trace = RetrievalTrace(
                structured=structured_trace,
                vector=self._skip_trace("structured_short_circuit"),
                fusion=self._skip_trace("structured_short_circuit"),
                ppr=self._skip_trace("structured_short_circuit"),
                total_ms=round((perf_counter() - total_start) * 1000.0, 2),
            )
            logger.info(
                "双路检索命中结构化短路：query_length=%s hit_count=%s",
                len(str(request.query or "")),
                len(short_circuit_hits[: request.top_k]),
            )
            return HybridRetrievalResult(
                hits=short_circuit_hits[: request.top_k],
                retrieval_mode="structured",
                trace=trace,
            )

        vector_hits: list[ParagraphHit]
        try:
            vector_hits, vector_trace = self.vector_retriever.retrieve(request, paragraph_ids=candidate_paragraph_ids)
        except StaleVectorIndexError:
            raise

        if not structured_hits and not vector_hits:
            trace = RetrievalTrace(
                structured=structured_trace,
                vector=vector_trace,
                fusion=self._skip_trace("no_hits"),
                ppr=self._skip_trace("no_hits"),
                total_ms=round((perf_counter() - total_start) * 1000.0, 2),
            )
            logger.info("双路检索未命中：query_length=%s", len(str(request.query or "")))
            return HybridRetrievalResult(hits=[], retrieval_mode="none", trace=trace)

        if structured_hits and not vector_hits:
            trace = RetrievalTrace(
                structured=structured_trace,
                vector=vector_trace,
                fusion=self._skip_trace("vector_empty"),
                ppr=self._skip_trace("vector_empty"),
                total_ms=round((perf_counter() - total_start) * 1000.0, 2),
            )
            logger.info(
                "双路检索完成：仅结构化命中，query_length=%s hit_count=%s",
                len(str(request.query or "")),
                len(structured_hits[: request.top_k]),
            )
            return HybridRetrievalResult(
                hits=structured_hits[: request.top_k],
                retrieval_mode="structured",
                trace=trace,
            )

        if vector_hits and not structured_hits:
            trace = RetrievalTrace(
                structured=structured_trace,
                vector=vector_trace,
                fusion=self._skip_trace("structured_empty"),
                ppr=self._skip_trace("structured_empty"),
                total_ms=round((perf_counter() - total_start) * 1000.0, 2),
            )
            logger.info(
                "双路检索完成：仅向量命中，query_length=%s hit_count=%s",
                len(str(request.query or "")),
                len(vector_hits[: request.top_k]),
            )
            return HybridRetrievalResult(
                hits=vector_hits[: request.top_k],
                retrieval_mode="vector",
                trace=trace,
            )

        fusion_start = perf_counter()
        fused_hits = self._weighted_rrf_fuse(structured_hits=structured_hits, vector_hits=vector_hits)
        fusion_trace = RetrievalLaneTrace(
            executed=True,
            skipped_reason=None,
            hit_count=len(fused_hits),
            latency_ms=round((perf_counter() - fusion_start) * 1000.0, 2),
            top_paragraph_ids=[hit.paragraph_id for hit in fused_hits[:6]],
        )
        retrieval_mode = "hybrid"
        final_hits = fused_hits[: request.top_k]
        highlighted_node_ids: list[str] = []
        highlighted_edge_ids: list[str] = []
        if self.settings.query_ppr_enabled and len(fused_hits) >= self.settings.query_ppr_min_hits:
            ppr_result = self.graph_reranker.rerank(fused_hits, candidate_limit=self.settings.query_ppr_candidate_limit)
            ppr_trace = ppr_result.trace
            if ppr_trace.executed:
                retrieval_mode = "hybrid_ppr"
                final_hits = ppr_result.hits[: request.top_k]
                highlighted_node_ids = ppr_result.highlighted_node_ids
                highlighted_edge_ids = ppr_result.highlighted_edge_ids
        else:
            ppr_trace = self._skip_trace("disabled_or_insufficient_hits")
        trace = RetrievalTrace(
            structured=structured_trace,
            vector=vector_trace,
            fusion=fusion_trace,
            ppr=ppr_trace,
            total_ms=round((perf_counter() - total_start) * 1000.0, 2),
        )
        logger.info(
            "双路检索完成：query_length=%s retrieval_mode=%s structured_hits=%s vector_hits=%s fused_hits=%s final_hits=%s ppr_executed=%s total_ms=%s",
            len(str(request.query or "")),
            retrieval_mode,
            len(structured_hits),
            len(vector_hits),
            len(fused_hits),
            len(final_hits),
            ppr_trace.executed,
            trace.total_ms,
        )
        return HybridRetrievalResult(
            hits=final_hits,
            retrieval_mode=retrieval_mode,
            trace=trace,
            highlighted_node_ids=highlighted_node_ids,
            highlighted_edge_ids=highlighted_edge_ids,
        )

    def _resolve_candidate_paragraph_ids(self, request: RetrievalRequest) -> list[str] | None:
        """按来源和工作表范围预先约束候选段落。"""

        if not request.worksheet_names:
            return None
        rows = self.record_store.list_candidate_rows(
            source_ids=request.source_ids or None,
            worksheet_names=request.worksheet_names or None,
            filters=None,
        )
        if not rows:
            return []
        paragraph_ids: list[str] = []
        seen: set[str] = set()
        for row in rows:
            paragraph_id = str(row.get("paragraph_id") or "")
            if not paragraph_id or paragraph_id in seen:
                continue
            seen.add(paragraph_id)
            paragraph_ids.append(paragraph_id)
        return paragraph_ids

    def _short_circuit_hits(self, request: RetrievalRequest, structured_hits: list[ParagraphHit]) -> list[ParagraphHit]:
        """判断结构化精确命中是否足以提前结束检索。"""

        if not structured_hits:
            return []
        required_hits = max(1, self.settings.query_structured_short_circuit_hits)
        candidate_hits = structured_hits[:required_hits]
        if len(candidate_hits) < required_hits:
            return []
        if all(hit.match_type in EXACT_MATCH_TYPES for hit in candidate_hits):
            return structured_hits[: request.top_k]
        return []

    def _weighted_rrf_fuse(self, *, structured_hits: list[ParagraphHit], vector_hits: list[ParagraphHit]) -> list[ParagraphHit]:
        """使用加权 RRF 融合结构化检索与向量检索结果。"""

        combined: dict[str, ParagraphHit] = {}
        combined_scores: dict[str, float] = {}
        origin_ranks: dict[str, dict[str, int]] = {}
        for weight, lane_name, lane_hits in (
            (1.0, "structured", structured_hits),
            (0.9, "vector", vector_hits),
        ):
            for rank, hit in enumerate(lane_hits, start=1):
                combined_scores[hit.paragraph_id] = combined_scores.get(hit.paragraph_id, 0.0) + (
                    weight / (self.settings.query_rrf_k + rank)
                )
                origin_ranks.setdefault(hit.paragraph_id, {})[lane_name] = rank
                if hit.paragraph_id not in combined:
                    combined[hit.paragraph_id] = hit
        fused_hits: list[ParagraphHit] = []
        for paragraph_id, score in combined_scores.items():
            base_hit = combined[paragraph_id]
            ranks = origin_ranks.get(paragraph_id, {})
            fused_hits.append(
                ParagraphHit(
                    paragraph_id=base_hit.paragraph_id,
                    source_id=base_hit.source_id,
                    score=round(score, 6),
                    rank=0,
                    retriever="hybrid",
                    match_type=base_hit.match_type if "structured" in ranks else "semantic",
                    metadata={
                        **dict(base_hit.metadata),
                        "origin_ranks": ranks,
                    },
                )
            )
        fused_hits.sort(key=lambda hit: (-hit.score, hit.paragraph_id))
        for index, hit in enumerate(fused_hits, start=1):
            hit.rank = index
        return fused_hits

    def _skip_trace(self, reason: str) -> RetrievalLaneTrace:
        """构造未执行链路的空轨迹。"""

        return RetrievalLaneTrace(
            executed=False,
            skipped_reason=reason,
            hit_count=0,
            latency_ms=0.0,
            top_paragraph_ids=[],
        )
