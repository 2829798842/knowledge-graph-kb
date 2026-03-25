"""Shared retrieval dataclasses for answer retrieval orchestration."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class RetrievalRequest:
    """Normalized retrieval request used across retrievers."""

    query: str
    source_ids: list[str] = field(default_factory=list)
    worksheet_names: list[str] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)
    top_k: int = 6


@dataclass(slots=True)
class ParagraphHit:
    """A paragraph-level hit returned by any retriever."""

    paragraph_id: str
    source_id: str
    score: float
    rank: int
    retriever: str
    match_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievalLaneTrace:
    """A single retriever or post-processing lane trace."""

    executed: bool
    skipped_reason: str | None
    hit_count: int
    latency_ms: float
    top_paragraph_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RetrievalTrace:
    """Full answer retrieval trace for structured, vector, fusion, and PPR lanes."""

    structured: RetrievalLaneTrace
    vector: RetrievalLaneTrace
    fusion: RetrievalLaneTrace
    ppr: RetrievalLaneTrace
    total_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "structured": self.structured.to_dict(),
            "vector": self.vector.to_dict(),
            "fusion": self.fusion.to_dict(),
            "ppr": self.ppr.to_dict(),
            "total_ms": self.total_ms,
        }


@dataclass(slots=True)
class HybridRetrievalResult:
    """Final retrieval result used by answer generation."""

    hits: list[ParagraphHit]
    retrieval_mode: str
    trace: RetrievalTrace
    highlighted_node_ids: list[str] = field(default_factory=list)
    highlighted_edge_ids: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

