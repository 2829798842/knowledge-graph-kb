"""模块名称：schemas.api.document_contracts

主要功能：定义文档上传、任务进度与文档详情相关的接口契约。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FileImportResponse(BaseModel):
    """文件上传响应模型。

    Attributes:
        job_id (str | None): 若上传后立即触发任务，则返回任务主键；否则为空。
        document_id (str): 对应文档的主键。
    """

    job_id: str | None = None
    document_id: str


class JobRead(BaseModel):
    """任务读取模型。

    Attributes:
        id (str): 任务主键。
        document_id (str): 关联文档主键。
        status (str): 当前任务状态。
        progress_percent (int): 当前进度百分比。
        stage (str): 当前处理阶段。
        status_message (str | None): 当前阶段的展示消息。
        error_message (str | None): 失败时的错误信息。
        created_at (datetime): 创建时间。
        updated_at (datetime): 更新时间。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    status: str
    progress_percent: int = 0
    stage: str = "queued"
    status_message: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentRead(BaseModel):
    """文档读取模型。

    Attributes:
        id (str): 文档主键。
        filename (str): 存储文件名。
        original_name (str): 原始文件名。
        file_type (str): 文件类型。
        status (str): 文档状态。
        summary (str | None): 文档摘要或统计信息。
        metadata (dict[str, Any]): 文档扩展信息。
        created_at (datetime): 创建时间。
        updated_at (datetime): 更新时间。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    original_name: str
    file_type: str
    status: str
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
