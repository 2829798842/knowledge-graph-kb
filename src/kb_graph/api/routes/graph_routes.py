"""模块名称：api.routes.graph_routes

主要功能：提供图谱查询、手工连边创建与删除接口。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from kb_graph.contracts.api.graph_contracts import CreateEdgeRequest, CreateEdgeResponse, GraphResponse
from kb_graph.data.database import get_session
from kb_graph.data.models import EdgeType, GraphEdge
from kb_graph.services.graph_service import build_graph_response, ensure_graph_edge, to_graph_edge_read

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    document_id: str | None = Query(default=None),
    include_chunks: bool = Query(default=True),
    limit: int = Query(default=300, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> GraphResponse:
    """查询图谱数据。

    Args:
        document_id: 可选的文档过滤条件。
        include_chunks: 是否返回切块节点。
        limit: 节点返回上限。
        session: 数据库会话。

    Returns:
        GraphResponse: 图谱节点与边数据。
    """

    return build_graph_response(
        session,
        document_id=document_id,
        include_chunks=include_chunks,
        limit=limit,
    )


@router.post("/edges", response_model=CreateEdgeResponse)
def create_edge(payload: CreateEdgeRequest, session: Session = Depends(get_session)) -> CreateEdgeResponse:
    """创建或更新手工连边。

    Args:
        payload: 连边请求参数。
        session: 数据库会话。

    Returns:
        CreateEdgeResponse: 创建后的边信息。
    """

    edge = ensure_graph_edge(
        session,
        source_node_id=payload.source_node_id,
        target_node_id=payload.target_node_id,
        edge_type=EdgeType.MANUAL,
        weight=payload.weight,
        metadata=payload.metadata,
    )
    session.commit()
    session.refresh(edge)
    return CreateEdgeResponse(edge=to_graph_edge_read(edge))


@router.delete("/edges/{edge_id}", response_model=dict[str, str])
def delete_edge(edge_id: str, session: Session = Depends(get_session)) -> dict[str, str]:
    """删除手工连边。

    Args:
        edge_id: 边主键。
        session: 数据库会话。

    Returns:
        dict[str, str]: 删除结果。

    Raises:
        HTTPException: 当边不存在时抛出。
    """

    edge = session.get(GraphEdge, edge_id)
    if edge is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    session.delete(edge)
    session.commit()
    return {"status": "deleted"}
