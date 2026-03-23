"""用于读取、测试与更新运行期模型配置的路由。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from src.api.dependencies import get_model_config_service
from src.config import get_settings
from src.data import get_session
from src.schemas.api import (
    ModelConfigurationRead,
    ModelConfigurationTestResult,
    TestModelConfigurationRequest,
    UpdateModelConfigurationRequest,
)
from src.services import ModelConfigurationService, OpenAiConfigurationError, OpenAiService

router = APIRouter(prefix="/api/model-config", tags=["model-config"])


@router.get("", response_model=ModelConfigurationRead)
def get_model_configuration(
    session: Session = Depends(get_session),
    model_config_service: ModelConfigurationService = Depends(get_model_config_service),
) -> ModelConfigurationRead:
    """返回当前可安全提供给前端的模型配置。"""

    return model_config_service.get_public_configuration(session)


@router.post("/test", response_model=ModelConfigurationTestResult)
def test_model_configuration(
    payload: TestModelConfigurationRequest,
    session: Session = Depends(get_session),
    model_config_service: ModelConfigurationService = Depends(get_model_config_service),
) -> ModelConfigurationTestResult:
    """在不保存的前提下校验供应商、API Key 与模型配置。"""

    try:
        runtime_config = model_config_service.build_runtime_configuration_for_test(session, payload)
        llm_ok, embedding_ok = OpenAiService(get_settings()).test_connection(runtime_config)
        return model_config_service.build_test_result(
            runtime_config,
            llm_ok=llm_ok,
            embedding_ok=embedding_ok,
        )
    except (ValueError, OpenAiConfigurationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("", response_model=ModelConfigurationRead)
def update_model_configuration(
    payload: UpdateModelConfigurationRequest,
    session: Session = Depends(get_session),
    model_config_service: ModelConfigurationService = Depends(get_model_config_service),
) -> ModelConfigurationRead:
    """持久化新的运行期模型配置。"""

    try:
        return model_config_service.update_configuration(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
