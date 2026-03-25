"""图谱相关路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_graph_service
from src.api.schemas import (
    GraphEdgeDetailResponse,
    GraphNodeDetailResponse,
    GraphResponse,
    ManualRelationItem,
    ManualRelationRequest,
    StatusResponse,
)

router = APIRouter(prefix="/api/kb/graph", tags=["kb-graph"])


@router.get("", response_model=GraphResponse)
def get_graph(
    source_ids: list[str] | None = Query(default=None),
    include_paragraphs: bool = Query(default=True),
    density: int = Query(default=100, ge=5, le=100),
    graph_service=Depends(get_graph_service),
) -> GraphResponse:
    return GraphResponse(**graph_service.build_graph(source_ids=source_ids, include_paragraphs=include_paragraphs, density=density))


@router.get("/nodes/{node_id}", response_model=GraphNodeDetailResponse)
def get_graph_node_detail(node_id: str, graph_service=Depends(get_graph_service)) -> GraphNodeDetailResponse:
    try:
        return GraphNodeDetailResponse(**graph_service.get_node_detail(node_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Graph node not found.") from exc


@router.get("/edges/{edge_id}", response_model=GraphEdgeDetailResponse)
def get_graph_edge_detail(edge_id: str, graph_service=Depends(get_graph_service)) -> GraphEdgeDetailResponse:
    try:
        return GraphEdgeDetailResponse(**graph_service.get_edge_detail(edge_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Graph edge not found.") from exc


@router.get("/manual-relations", response_model=list[ManualRelationItem])
def list_manual_relations(graph_service=Depends(get_graph_service)) -> list[ManualRelationItem]:
    return [ManualRelationItem(**item) for item in graph_service.list_manual_relations()]


@router.post("/manual-relations", response_model=ManualRelationItem)
def create_manual_relation(
    payload: ManualRelationRequest,
    graph_service=Depends(get_graph_service),
) -> ManualRelationItem:
    relation = graph_service.create_manual_relation(
        subject_node_id=payload.subject_node_id,
        predicate=payload.predicate,
        object_node_id=payload.object_node_id,
        weight=payload.weight,
        metadata=payload.metadata,
    )
    return ManualRelationItem(**relation)


@router.delete("/manual-relations/{relation_id}", response_model=StatusResponse)
def delete_manual_relation(relation_id: str, graph_service=Depends(get_graph_service)) -> StatusResponse:
    if not graph_service.delete_manual_relation(relation_id):
        raise HTTPException(status_code=404, detail="Manual relation not found.")
    return StatusResponse(status="deleted")
