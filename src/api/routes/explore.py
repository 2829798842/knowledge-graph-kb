"""图谱与来源浏览相关路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_graph_service, get_source_service
from src.api.schemas import (
    GraphEdgeDetailResponse,
    GraphNodeDetailResponse,
    GraphResponse,
    ManualRelationItem,
    ManualRelationRequest,
    SourceDetailResponse,
    SourceItem,
    SourceParagraphsResponse,
    StatusResponse,
)

graph_router = APIRouter(prefix="/api/kb/graph", tags=["kb-graph"])
source_router = APIRouter(prefix="/api/kb/sources", tags=["kb-sources"])


@graph_router.get("", response_model=GraphResponse)
def get_graph(
    source_ids: list[str] | None = Query(default=None),
    include_paragraphs: bool = Query(default=True),
    density: int = Query(default=100, ge=5, le=100),
    graph_service=Depends(get_graph_service),
) -> GraphResponse:
    return GraphResponse(**graph_service.build_graph(source_ids=source_ids, include_paragraphs=include_paragraphs, density=density))


@graph_router.get("/nodes/{node_id}", response_model=GraphNodeDetailResponse)
def get_graph_node_detail(node_id: str, graph_service=Depends(get_graph_service)) -> GraphNodeDetailResponse:
    try:
        return GraphNodeDetailResponse(**graph_service.get_node_detail(node_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Graph node not found.") from exc


@graph_router.get("/edges/{edge_id}", response_model=GraphEdgeDetailResponse)
def get_graph_edge_detail(edge_id: str, graph_service=Depends(get_graph_service)) -> GraphEdgeDetailResponse:
    try:
        return GraphEdgeDetailResponse(**graph_service.get_edge_detail(edge_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Graph edge not found.") from exc


@graph_router.get("/manual-relations", response_model=list[ManualRelationItem])
def list_manual_relations(graph_service=Depends(get_graph_service)) -> list[ManualRelationItem]:
    return [ManualRelationItem(**item) for item in graph_service.list_manual_relations()]


@graph_router.post("/manual-relations", response_model=ManualRelationItem)
def create_manual_relation(
    payload: ManualRelationRequest,
    graph_service=Depends(get_graph_service),
) -> ManualRelationItem:
    try:
        relation = graph_service.create_manual_relation(
            subject_node_id=payload.subject_node_id,
            predicate=payload.predicate,
            object_node_id=payload.object_node_id,
            weight=payload.weight,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ManualRelationItem(**relation)


@graph_router.delete("/manual-relations/{relation_id}", response_model=StatusResponse)
def delete_manual_relation(relation_id: str, graph_service=Depends(get_graph_service)) -> StatusResponse:
    if not graph_service.delete_manual_relation(relation_id):
        raise HTTPException(status_code=404, detail="Manual relation not found.")
    return StatusResponse(status="deleted")


@source_router.get("", response_model=list[SourceItem])
def list_sources(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    source_service=Depends(get_source_service),
) -> list[SourceItem]:
    return [SourceItem(**item) for item in source_service.list_sources(keyword=keyword, limit=limit)]


@source_router.get("/{source_id}", response_model=SourceDetailResponse)
def get_source_detail(source_id: str, source_service=Depends(get_source_service)) -> SourceDetailResponse:
    detail = source_service.get_source_detail(source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return SourceDetailResponse(**detail)


@source_router.get("/{source_id}/paragraphs", response_model=SourceParagraphsResponse)
def list_source_paragraphs(source_id: str, source_service=Depends(get_source_service)) -> SourceParagraphsResponse:
    paragraphs = source_service.list_source_paragraphs(source_id)
    if paragraphs is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return SourceParagraphsResponse(items=paragraphs)
