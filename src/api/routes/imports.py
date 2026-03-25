"""导入任务相关路由。"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from src.api.dependencies import get_import_service
from src.api.schemas import (
    ImportJobChunkItem,
    ImportJobItem,
    ImportJobResponse,
    PasteImportRequest,
    ScanImportRequest,
    StructuredImportRequest,
)

router = APIRouter(prefix="/api/kb/imports", tags=["kb-imports"])


@router.get("/jobs", response_model=list[ImportJobItem])
def list_import_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    import_service=Depends(get_import_service),
) -> list[ImportJobItem]:
    """返回最近的导入任务列表。"""

    return [ImportJobItem(**job) for job in import_service.list_jobs(limit=limit)]


@router.post("/uploads", response_model=ImportJobResponse)
async def submit_upload_import(
    files: list[UploadFile] = File(...),
    strategy: str = "auto",
    import_service=Depends(get_import_service),
) -> ImportJobResponse:
    """提交上传文件导入任务。"""

    try:
        file_payloads = [(file.filename or "upload.txt", await file.read(), file.content_type) for file in files]
        job = import_service.submit_uploads(files=file_payloads, strategy=strategy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.post("/paste", response_model=ImportJobResponse)
def submit_paste_import(
    payload: PasteImportRequest,
    import_service=Depends(get_import_service),
) -> ImportJobResponse:
    """提交粘贴文本导入任务。"""

    try:
        job = import_service.submit_paste(
            title=payload.title,
            content=payload.content,
            strategy=payload.strategy,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.post("/scan", response_model=ImportJobResponse)
def submit_scan_import(
    payload: ScanImportRequest,
    import_service=Depends(get_import_service),
) -> ImportJobResponse:
    """提交扫描目录导入任务。"""

    try:
        job = import_service.submit_scan(
            root_path=payload.root_path,
            glob_pattern=payload.glob_pattern,
            strategy=payload.strategy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.post("/openie", response_model=ImportJobResponse)
def submit_openie_import(
    payload: StructuredImportRequest,
    import_service=Depends(get_import_service),
) -> ImportJobResponse:
    """提交 OpenIE 结构化导入任务。"""

    try:
        job = import_service.submit_openie(
            title=payload.title,
            payload=payload.payload,
            strategy=payload.strategy,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.post("/convert", response_model=ImportJobResponse)
def submit_convert_import(
    payload: StructuredImportRequest,
    import_service=Depends(get_import_service),
) -> ImportJobResponse:
    """提交转换结果导入任务。"""

    try:
        job = import_service.submit_convert(
            title=payload.title,
            payload=payload.payload,
            strategy=payload.strategy,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.get("/jobs/{job_id}", response_model=ImportJobItem)
def get_import_job(job_id: str, import_service=Depends(get_import_service)) -> ImportJobItem:
    """读取单个导入任务详情。"""

    job = import_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="未找到导入任务。")
    return ImportJobItem(**job)


@router.get("/jobs/{job_id}/files/{file_id}/chunks", response_model=list[ImportJobChunkItem])
def list_import_chunks(job_id: str, file_id: str, import_service=Depends(get_import_service)) -> list[ImportJobChunkItem]:
    """列出指定导入文件的分块处理记录。"""

    job = import_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="未找到导入任务。")
    file_exists = any(str(file_row["id"]) == file_id for file_row in list(job.get("files") or []))
    if not file_exists:
        raise HTTPException(status_code=404, detail="未找到导入文件。")
    return [ImportJobChunkItem(**chunk) for chunk in import_service.list_job_chunks(job_id, file_id)]


@router.post("/jobs/{job_id}/cancel", response_model=ImportJobItem)
def cancel_import_job(job_id: str, import_service=Depends(get_import_service)) -> ImportJobItem:
    """取消指定导入任务。"""

    job = import_service.cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="未找到导入任务。")
    return ImportJobItem(**job)


@router.post("/jobs/{job_id}/retry", response_model=ImportJobResponse)
def retry_import_job(job_id: str, import_service=Depends(get_import_service)) -> ImportJobResponse:
    """重试指定任务中的异常文件。"""

    try:
        job = import_service.retry_failed(job_id)
    except ValueError as exc:
        status_code = 404 if "未找到" in str(exc) or "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))
