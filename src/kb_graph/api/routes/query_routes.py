"""模块名称：api.routes.query_routes

主要功能：提供知识库问答查询接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from kb_graph.api.dependencies import get_query_service
from kb_graph.contracts.api.query_contracts import QueryRequest, QueryResponse
from kb_graph.data.database import get_session
from kb_graph.services.openai_service import OpenAiConfigurationError
from kb_graph.services.query_service import QueryService

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query_knowledge_base(
    payload: QueryRequest,
    session: Session = Depends(get_session),
    query_service: QueryService = Depends(get_query_service),
) -> QueryResponse:
    """执行知识库问答查询。

    Args:
        payload: 查询请求参数。
        session: 数据库会话。
        query_service: 问答检索服务。

    Returns:
        QueryResponse: 问答查询结果。

    Raises:
        HTTPException: 当 OpenAI 未配置时抛出。
    """

    try:
        return query_service.answer(
            session,
            query=payload.query,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
        )
    except OpenAiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
