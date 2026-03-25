"""查询与对话相关路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import (
    get_conversation_service,
    get_entity_search_service,
    get_record_search_service,
    get_relation_search_service,
    get_source_search_service,
)
from src.api.schemas import (
    ChatMessageCreateRequest,
    ChatMessageItem,
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionItem,
    EntitySearchRequest,
    EntitySearchResponse,
    RecordSearchRequest,
    RecordSearchResponse,
    RelationSearchRequest,
    RelationSearchResponse,
    SourceSearchRequest,
    SourceSearchResponse,
)
from src.kb.providers import OpenAiConfigurationError, OpenAiRequestError

chat_router = APIRouter(prefix="/api/kb/chat", tags=["kb-chat"])
search_router = APIRouter(prefix="/api/kb/search", tags=["kb-search"])


@chat_router.get("/sessions", response_model=list[ChatSessionItem])
def list_chat_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    conversation_service=Depends(get_conversation_service),
) -> list[ChatSessionItem]:
    """返回最近的问答会话列表。"""

    return [ChatSessionItem(**session) for session in conversation_service.list_sessions(limit=limit)]


@chat_router.post("/sessions", response_model=ChatSessionItem)
def create_chat_session(
    payload: ChatSessionCreateRequest,
    conversation_service=Depends(get_conversation_service),
) -> ChatSessionItem:
    """创建新的问答会话。"""

    return ChatSessionItem(**conversation_service.create_session(title=payload.title, metadata=payload.metadata))


@chat_router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_chat_session(
    session_id: str,
    conversation_service=Depends(get_conversation_service),
) -> ChatSessionDetailResponse:
    """返回指定会话及其消息详情。"""

    session = conversation_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="未找到问答会话。")
    return ChatSessionDetailResponse(
        session=ChatSessionItem(**{key: value for key, value in session.items() if key != "messages"}),
        messages=[ChatMessageItem(**message) for message in list(session.get("messages") or [])],
    )


@chat_router.post("/sessions/{session_id}/messages", response_model=ChatSessionDetailResponse)
def create_chat_message(
    session_id: str,
    payload: ChatMessageCreateRequest,
    conversation_service=Depends(get_conversation_service),
) -> ChatSessionDetailResponse:
    """写入一条用户消息，并返回更新后的会话详情。"""

    try:
        session = conversation_service.post_user_message(
            session_id=session_id,
            content=payload.content,
            source_ids=payload.source_ids,
            worksheet_names=payload.worksheet_names,
            top_k=payload.top_k,
        )
    except OpenAiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpenAiRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        if "问答会话" in str(exc) or "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChatSessionDetailResponse(
        session=ChatSessionItem(**{key: value for key, value in session.items() if key != "messages"}),
        messages=[ChatMessageItem(**message) for message in list(session.get("messages") or [])],
    )


@search_router.post("/records", response_model=RecordSearchResponse)
def search_records(payload: RecordSearchRequest, record_search_service=Depends(get_record_search_service)) -> RecordSearchResponse:
    """执行表格记录检索。"""

    try:
        result = record_search_service.search_records(
            query=payload.query,
            source_ids=payload.source_ids,
            worksheet_names=payload.worksheet_names,
            filters=payload.filters,
            limit=payload.limit,
        )
    except OpenAiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpenAiRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RecordSearchResponse(**result)


@search_router.post("/entities", response_model=EntitySearchResponse)
def search_entities(payload: EntitySearchRequest, entity_search_service=Depends(get_entity_search_service)) -> EntitySearchResponse:
    """执行实体检索。"""

    return EntitySearchResponse(**entity_search_service.search_entities(query=payload.query, limit=payload.limit))


@search_router.post("/relations", response_model=RelationSearchResponse)
def search_relations(payload: RelationSearchRequest, relation_search_service=Depends(get_relation_search_service)) -> RelationSearchResponse:
    """执行关系检索。"""

    return RelationSearchResponse(**relation_search_service.search_relations(query=payload.query, limit=payload.limit))


@search_router.post("/sources", response_model=SourceSearchResponse)
def search_sources(payload: SourceSearchRequest, source_search_service=Depends(get_source_search_service)) -> SourceSearchResponse:
    """执行来源检索。"""

    return SourceSearchResponse(**source_search_service.search_sources(query=payload.query, limit=payload.limit))
