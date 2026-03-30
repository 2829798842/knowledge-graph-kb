"""Query and chat routes."""
from fastapi import APIRouter, Depends, Query

from src.api.dependencies import (
    get_conversation_service,
    get_entity_search_service,
    get_record_search_service,
    get_relation_search_service,
    get_source_search_service,
)
from src.api.errors import api_error
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
    return [ChatSessionItem(**session) for session in conversation_service.list_sessions(limit=limit)]


@chat_router.post("/sessions", response_model=ChatSessionItem)
def create_chat_session(
    payload: ChatSessionCreateRequest,
    conversation_service=Depends(get_conversation_service),
) -> ChatSessionItem:
    return ChatSessionItem(**conversation_service.create_session(title=payload.title, metadata=payload.metadata))


@chat_router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_chat_session(session_id: str, conversation_service=Depends(get_conversation_service)) -> ChatSessionDetailResponse:
    session = conversation_service.get_session(session_id)
    if session is None:
        raise api_error(status_code=404, code="chat_session_not_found", message="Chat session not found.")
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
    try:
        session = conversation_service.post_user_message(
            session_id=session_id,
            content=payload.content,
            source_ids=payload.source_ids,
            worksheet_names=payload.worksheet_names,
            top_k=payload.top_k,
        )
    except OpenAiConfigurationError as exc:
        raise api_error(status_code=503, code="model_config_error", message=str(exc)) from exc
    except OpenAiRequestError as exc:
        raise api_error(status_code=exc.status_code, code="model_request_error", message=str(exc)) from exc
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower() or "会话" in message:
            raise api_error(status_code=404, code="chat_session_not_found", message=message) from exc
        raise api_error(status_code=400, code="invalid_chat_request", message=message) from exc
    return ChatSessionDetailResponse(
        session=ChatSessionItem(**{key: value for key, value in session.items() if key != "messages"}),
        messages=[ChatMessageItem(**message) for message in list(session.get("messages") or [])],
    )


@search_router.post("/records", response_model=RecordSearchResponse)
def search_records(
    payload: RecordSearchRequest,
    record_search_service=Depends(get_record_search_service),
) -> RecordSearchResponse:
    try:
        result = record_search_service.search_records(
            query=payload.query,
            source_ids=payload.source_ids,
            worksheet_names=payload.worksheet_names,
            filters=payload.filters,
            limit=payload.limit,
        )
    except OpenAiConfigurationError as exc:
        raise api_error(status_code=503, code="model_config_error", message=str(exc)) from exc
    except OpenAiRequestError as exc:
        raise api_error(status_code=exc.status_code, code="model_request_error", message=str(exc)) from exc
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_record_search", message=str(exc)) from exc
    return RecordSearchResponse(**result)


@search_router.post("/entities", response_model=EntitySearchResponse)
def search_entities(payload: EntitySearchRequest, entity_search_service=Depends(get_entity_search_service)) -> EntitySearchResponse:
    return EntitySearchResponse(**entity_search_service.search_entities(query=payload.query, limit=payload.limit))


@search_router.post("/relations", response_model=RelationSearchResponse)
def search_relations(
    payload: RelationSearchRequest,
    relation_search_service=Depends(get_relation_search_service),
) -> RelationSearchResponse:
    return RelationSearchResponse(**relation_search_service.search_relations(query=payload.query, limit=payload.limit))


@search_router.post("/sources", response_model=SourceSearchResponse)
def search_sources(payload: SourceSearchRequest, source_search_service=Depends(get_source_search_service)) -> SourceSearchResponse:
    return SourceSearchResponse(**source_search_service.search_sources(query=payload.query, limit=payload.limit))
