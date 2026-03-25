"""检索与问答相关路由。"""

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_search_service
from src.api.schemas import (
    AnswerRequest,
    AnswerResponse,
    EntitySearchRequest,
    EntitySearchResponse,
    RecordSearchRequest,
    RecordSearchResponse,
    RelationSearchRequest,
    RelationSearchResponse,
    SourceSearchRequest,
    SourceSearchResponse,
)
from src.knowledge_base.infrastructure.openai_gateway import OpenAiConfigurationError, OpenAiRequestError

router = APIRouter(prefix="/api/kb/search", tags=["kb-search"])


@router.post("/answer", response_model=AnswerResponse)
def answer_query(payload: AnswerRequest, search_service=Depends(get_search_service)) -> AnswerResponse:
    try:
        result = search_service.answer(
            query=payload.query,
            source_ids=payload.source_ids,
            worksheet_names=payload.worksheet_names,
            exact_first=payload.exact_first,
            top_k=payload.top_k,
        )
    except OpenAiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpenAiRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AnswerResponse(**result)


@router.post("/records", response_model=RecordSearchResponse)
def search_records(payload: RecordSearchRequest, search_service=Depends(get_search_service)) -> RecordSearchResponse:
    try:
        result = search_service.search_records(
            query=payload.query,
            source_ids=payload.source_ids,
            worksheet_names=payload.worksheet_names,
            filters=payload.filters,
            limit=payload.limit,
            mode=payload.mode,
        )
    except OpenAiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpenAiRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RecordSearchResponse(**result)


@router.post("/entities", response_model=EntitySearchResponse)
def search_entities(payload: EntitySearchRequest, search_service=Depends(get_search_service)) -> EntitySearchResponse:
    return EntitySearchResponse(**search_service.search_entities(query=payload.query, limit=payload.limit))


@router.post("/relations", response_model=RelationSearchResponse)
def search_relations(payload: RelationSearchRequest, search_service=Depends(get_search_service)) -> RelationSearchResponse:
    return RelationSearchResponse(**search_service.search_relations(query=payload.query, limit=payload.limit))


@router.post("/sources", response_model=SourceSearchResponse)
def search_sources(payload: SourceSearchRequest, search_service=Depends(get_search_service)) -> SourceSearchResponse:
    return SourceSearchResponse(**search_service.search_sources(query=payload.query, limit=payload.limit))
