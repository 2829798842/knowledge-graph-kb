"""Import job routes."""
from fastapi import APIRouter, Depends, File, UploadFile

from src.api.dependencies import get_import_service
from src.api.errors import api_error
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
def list_import_jobs(limit: int = 50, import_service=Depends(get_import_service)) -> list[ImportJobItem]:
    return [ImportJobItem(**job) for job in import_service.list_jobs(limit=limit)]


@router.post("/uploads", response_model=ImportJobResponse)
async def submit_upload_import(
    files: list[UploadFile] = File(...),
    strategy: str = "auto",
    import_service=Depends(get_import_service),
) -> ImportJobResponse:
    try:
        file_payloads = [(file.filename or "upload.txt", await file.read(), file.content_type) for file in files]
        job = import_service.submit_uploads(files=file_payloads, strategy=strategy)
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_import_request", message=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.post("/paste", response_model=ImportJobResponse)
def submit_paste_import(payload: PasteImportRequest, import_service=Depends(get_import_service)) -> ImportJobResponse:
    try:
        job = import_service.submit_paste(
            title=payload.title,
            content=payload.content,
            strategy=payload.strategy,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_import_request", message=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.post("/scan", response_model=ImportJobResponse)
def submit_scan_import(payload: ScanImportRequest, import_service=Depends(get_import_service)) -> ImportJobResponse:
    try:
        job = import_service.submit_scan(
            root_path=payload.root_path,
            glob_pattern=payload.glob_pattern,
            strategy=payload.strategy,
        )
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_import_request", message=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.post("/openie", response_model=ImportJobResponse)
def submit_openie_import(payload: StructuredImportRequest, import_service=Depends(get_import_service)) -> ImportJobResponse:
    try:
        job = import_service.submit_openie(
            title=payload.title,
            payload=payload.payload,
            strategy=payload.strategy,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_import_request", message=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.post("/convert", response_model=ImportJobResponse)
def submit_convert_import(payload: StructuredImportRequest, import_service=Depends(get_import_service)) -> ImportJobResponse:
    try:
        job = import_service.submit_convert(
            title=payload.title,
            payload=payload.payload,
            strategy=payload.strategy,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise api_error(status_code=400, code="invalid_import_request", message=str(exc)) from exc
    return ImportJobResponse(job=ImportJobItem(**job))


@router.get("/jobs/{job_id}", response_model=ImportJobItem)
def get_import_job(job_id: str, import_service=Depends(get_import_service)) -> ImportJobItem:
    job = import_service.get_job(job_id)
    if job is None:
        raise api_error(status_code=404, code="import_job_not_found", message="Import job not found.")
    return ImportJobItem(**job)


@router.get("/jobs/{job_id}/files/{file_id}/chunks", response_model=list[ImportJobChunkItem])
def list_import_chunks(job_id: str, file_id: str, import_service=Depends(get_import_service)) -> list[ImportJobChunkItem]:
    job = import_service.get_job(job_id)
    if job is None:
        raise api_error(status_code=404, code="import_job_not_found", message="Import job not found.")
    file_exists = any(str(file_row["id"]) == file_id for file_row in list(job.get("files") or []))
    if not file_exists:
        raise api_error(status_code=404, code="import_file_not_found", message="Import file not found.")
    return [ImportJobChunkItem(**chunk) for chunk in import_service.list_job_chunks(job_id, file_id)]


@router.post("/jobs/{job_id}/cancel", response_model=ImportJobItem)
def cancel_import_job(job_id: str, import_service=Depends(get_import_service)) -> ImportJobItem:
    job = import_service.cancel_job(job_id)
    if job is None:
        raise api_error(status_code=404, code="import_job_not_found", message="Import job not found.")
    return ImportJobItem(**job)


@router.post("/jobs/{job_id}/retry", response_model=ImportJobResponse)
def retry_import_job(job_id: str, import_service=Depends(get_import_service)) -> ImportJobResponse:
    try:
        job = import_service.retry_failed(job_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() or "未找到" in message else 400
        code = "import_job_not_found" if status_code == 404 else "invalid_import_retry"
        raise api_error(status_code=status_code, code=code, message=message) from exc
    return ImportJobResponse(job=ImportJobItem(**job))
