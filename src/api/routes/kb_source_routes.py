"""知识源浏览相关路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_source_service
from src.api.schemas import SourceDetailResponse, SourceItem, SourceParagraphsResponse

router = APIRouter(prefix="/api/kb/sources", tags=["kb-sources"])


@router.get("", response_model=list[SourceItem])
def list_sources(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    source_service=Depends(get_source_service),
) -> list[SourceItem]:
    return [SourceItem(**item) for item in source_service.list_sources(keyword=keyword, limit=limit)]


@router.get("/{source_id}", response_model=SourceDetailResponse)
def get_source_detail(source_id: str, source_service=Depends(get_source_service)) -> SourceDetailResponse:
    detail = source_service.get_source_detail(source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return SourceDetailResponse(**detail)


@router.get("/{source_id}/paragraphs", response_model=SourceParagraphsResponse)
def list_source_paragraphs(source_id: str, source_service=Depends(get_source_service)) -> SourceParagraphsResponse:
    paragraphs = source_service.list_source_paragraphs(source_id)
    if paragraphs is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return SourceParagraphsResponse(items=paragraphs)
