"""模块名称：api.routes.document_routes

主要功能：提供文件上传、手动开始抽取、任务查询与文档列表接口。
"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from src.api.dependencies import get_ingestion_service
from src.config import get_settings
from src.data import (
    Document,
    DocumentStatus,
    IngestionJob,
    JobStatus,
    get_engine,
    get_session,
    utc_now,
)
from src.schemas.api import DocumentRead, FileImportResponse, JobRead
from src.services import IngestionService
from src.services.graph_service import seed_document_node
from src.services.parser_service import SUPPORTED_EXTENSIONS
from src.utils.file_utils import sanitize_filename

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/files/import", response_model=FileImportResponse)
async def import_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> FileImportResponse:
    """上传文件并创建文档记录。

    Args:
        file: 上传文件对象。
        session: 数据库会话。

    Returns:
        FileImportResponse: 已创建的文档标识。

    Raises:
        HTTPException: 当文件类型不受支持时抛出。
    """

    settings = get_settings()
    original_name: str = file.filename or "upload"
    suffix: str = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed_text: str = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed_text}")

    saved_name: str = f"{uuid4()}_{sanitize_filename(original_name)}"
    destination: Path = settings.resolved_upload_dir / saved_name
    contents: bytes = await file.read()
    destination.write_bytes(contents)

    document = Document(
        filename=saved_name,
        original_name=original_name,
        file_type=suffix.removeprefix("."),
        content_type=file.content_type,
        storage_path=str(destination),
        status=DocumentStatus.QUEUED,
        metadata_json={"size_bytes": len(contents)},
    )
    session.add(document)
    seed_document_node(session, document)
    session.commit()

    return FileImportResponse(job_id=None, document_id=document.id)


@router.post("/documents/{document_id}/extract", response_model=JobRead)
def start_document_extraction(
    document_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> JobRead:
    """为指定文档启动一次抽取任务。

    Args:
        document_id: 文档主键。
        background_tasks: FastAPI 后台任务管理器。
        session: 数据库会话。

    Returns:
        JobRead: 已创建或已存在的活动任务详情。

    Raises:
        HTTPException: 当文档不存在时抛出。
    """

    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    active_job = _find_active_job(session, document_id=document_id)
    if active_job is not None:
        return JobRead.model_validate(active_job)

    updated_at = utc_now()
    document.status = DocumentStatus.QUEUED
    document.updated_at = updated_at
    job = IngestionJob(
        document_id=document.id,
        status=JobStatus.PENDING,
        progress_percent=0,
        stage="queued",
        status_message="等待开始抽取",
        error_message=None,
        updated_at=updated_at,
    )
    session.add(document)
    session.add(job)
    session.commit()
    session.refresh(job)

    background_tasks.add_task(run_ingestion_job, job.id, document.id)
    return JobRead.model_validate(job)


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(session: Session = Depends(get_session)) -> list[JobRead]:
    """返回最近的导入任务列表。

    Args:
        session: 数据库会话。

    Returns:
        list[JobRead]: 按创建时间倒序排列的任务列表。
    """

    jobs: list[IngestionJob] = list(session.exec(select(IngestionJob)).all())
    jobs.sort(key=lambda job: job.created_at, reverse=True)
    return [JobRead.model_validate(job) for job in jobs[:30]]


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str, session: Session = Depends(get_session)) -> JobRead:
    """读取导入任务状态。

    Args:
        job_id: 导入任务主键。
        session: 数据库会话。

    Returns:
        JobRead: 任务状态详情。

    Raises:
        HTTPException: 当任务不存在时抛出。
    """

    job = session.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobRead.model_validate(job)


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(session: Session = Depends(get_session)) -> list[DocumentRead]:
    """返回文档列表。

    Args:
        session: 数据库会话。

    Returns:
        list[DocumentRead]: 文档列表。
    """

    documents: list[Document] = list(session.exec(select(Document)).all())
    documents.sort(key=lambda document: document.created_at, reverse=True)
    return [
        DocumentRead(
            id=document.id,
            filename=document.filename,
            original_name=document.original_name,
            file_type=document.file_type,
            status=document.status,
            summary=document.summary,
            metadata=document.metadata_json,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        for document in documents
    ]


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, session: Session = Depends(get_session)) -> DocumentRead:
    """读取单个文档详情。

    Args:
        document_id: 文档主键。
        session: 数据库会话。

    Returns:
        DocumentRead: 文档详情。

    Raises:
        HTTPException: 当文档不存在时抛出。
    """

    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentRead(
        id=document.id,
        filename=document.filename,
        original_name=document.original_name,
        file_type=document.file_type,
        status=document.status,
        summary=document.summary,
        metadata=document.metadata_json,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def run_ingestion_job(job_id: str, document_id: str) -> None:
    """执行后台导入任务。

    Args:
        job_id: 导入任务主键。
        document_id: 文档主键。
    """

    service: IngestionService = get_ingestion_service()
    with Session(get_engine()) as session:
        service.process_document(session, job_id=job_id, document_id=document_id)


def _find_active_job(session: Session, *, document_id: str) -> IngestionJob | None:
    """查找文档当前仍处于进行中的任务。

    Args:
        session: 数据库会话。
        document_id: 文档主键。

    Returns:
        IngestionJob | None: 若存在活动任务则返回该任务，否则返回 `None`。
    """

    jobs: list[IngestionJob] = list(session.exec(select(IngestionJob).where(IngestionJob.document_id == document_id)).all())
    active_jobs: list[IngestionJob] = [
        job for job in jobs if job.status in {JobStatus.PENDING, JobStatus.PROCESSING}
    ]
    if not active_jobs:
        return None
    active_jobs.sort(key=lambda job: job.created_at, reverse=True)
    return active_jobs[0]
