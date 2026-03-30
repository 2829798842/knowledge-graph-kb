"""Knowledge-graph and source browsing routes."""
from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_graph_service, get_source_service
from src.api.errors import api_error
from src.api.schemas import (
    GraphEdgeDetailResponse,
    GraphNodeCreateRequest,
    GraphNodeDetailResponse,
    GraphNodeItem,
    GraphNodeUpdateRequest,
    GraphResponse,
    ManualRelationItem,
    ManualRelationRequest,
    SourceDetailResponse,
    SourceItem,
    SourceParagraphsResponse,
    SourceUpdateRequest,
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
    return GraphResponse(
        **graph_service.build_graph(
            source_ids=source_ids,
            include_paragraphs=include_paragraphs,
            density=density,
        )
    )


@graph_router.post("/nodes", response_model=GraphNodeItem)
def create_graph_node(
    payload: GraphNodeCreateRequest,
    graph_service=Depends(get_graph_service),
) -> GraphNodeItem:
    try:
        node = graph_service.create_manual_entity(
            label=payload.label,
            description=payload.description,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_graph_node", message=str(exc)) from exc
    return GraphNodeItem(**node)


@graph_router.get("/nodes/{node_id}", response_model=GraphNodeDetailResponse)
def get_graph_node_detail(node_id: str, graph_service=Depends(get_graph_service)) -> GraphNodeDetailResponse:
    try:
        return GraphNodeDetailResponse(**graph_service.get_node_detail(node_id))
    except KeyError as exc:
        raise api_error(status_code=404, code="graph_node_not_found", message="Graph node not found.") from exc


@graph_router.put("/nodes/{node_id}", response_model=StatusResponse)
def update_graph_node(
    node_id: str,
    payload: GraphNodeUpdateRequest,
    graph_service=Depends(get_graph_service),
) -> StatusResponse:
    try:
        graph_service.update_node_label(node_id, payload.label)
    except KeyError as exc:
        raise api_error(status_code=404, code="graph_node_not_found", message="Graph node not found.") from exc
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_graph_node", message=str(exc)) from exc
    return StatusResponse(status="updated")


@graph_router.delete("/nodes/{node_id}", response_model=StatusResponse)
def delete_graph_node(node_id: str, graph_service=Depends(get_graph_service)) -> StatusResponse:
    try:
        graph_service.delete_node(node_id)
    except KeyError as exc:
        raise api_error(status_code=404, code="graph_node_not_found", message="Graph node not found.") from exc
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_graph_node", message=str(exc)) from exc
    return StatusResponse(status="deleted")


@graph_router.get("/edges/{edge_id}", response_model=GraphEdgeDetailResponse)
def get_graph_edge_detail(edge_id: str, graph_service=Depends(get_graph_service)) -> GraphEdgeDetailResponse:
    try:
        return GraphEdgeDetailResponse(**graph_service.get_edge_detail(edge_id))
    except KeyError as exc:
        raise api_error(status_code=404, code="graph_edge_not_found", message="Graph edge not found.") from exc


@graph_router.delete("/edges/{edge_id}", response_model=StatusResponse)
def delete_graph_edge(edge_id: str, graph_service=Depends(get_graph_service)) -> StatusResponse:
    try:
        graph_service.delete_edge(edge_id)
    except KeyError as exc:
        raise api_error(status_code=404, code="graph_edge_not_found", message="Graph edge not found.") from exc
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_graph_edge", message=str(exc)) from exc
    return StatusResponse(status="deleted")


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
        raise api_error(status_code=400, code="invalid_manual_relation", message=str(exc)) from exc
    return ManualRelationItem(**relation)


@graph_router.delete("/manual-relations/{relation_id}", response_model=StatusResponse)
def delete_manual_relation(relation_id: str, graph_service=Depends(get_graph_service)) -> StatusResponse:
    if not graph_service.delete_manual_relation(relation_id):
        raise api_error(status_code=404, code="manual_relation_not_found", message="Manual relation not found.")
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
        raise api_error(status_code=404, code="source_not_found", message="Source not found.")
    return SourceDetailResponse(**detail)


@source_router.put("/{source_id}", response_model=SourceItem)
def update_source(
    source_id: str,
    payload: SourceUpdateRequest,
    source_service=Depends(get_source_service),
) -> SourceItem:
    try:
        source = source_service.update_source(
            source_id,
            name=payload.name,
            summary=payload.summary,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_source", message=str(exc)) from exc
    if source is None:
        raise api_error(status_code=404, code="source_not_found", message="Source not found.")
    return SourceItem(**source)


@source_router.delete("/{source_id}", response_model=StatusResponse)
def delete_source(source_id: str, graph_service=Depends(get_graph_service)) -> StatusResponse:
    try:
        graph_service.delete_source(source_id)
    except KeyError as exc:
        raise api_error(status_code=404, code="source_not_found", message="Source not found.") from exc
    return StatusResponse(status="deleted")


@source_router.get("/{source_id}/paragraphs", response_model=SourceParagraphsResponse)
def list_source_paragraphs(source_id: str, source_service=Depends(get_source_service)) -> SourceParagraphsResponse:
    paragraphs = source_service.list_source_paragraphs(source_id)
    if paragraphs is None:
        raise api_error(status_code=404, code="source_not_found", message="Source not found.")
    return SourceParagraphsResponse(items=paragraphs)
