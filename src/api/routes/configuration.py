"""模型配置相关路由。"""

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_model_config_service, get_openai_gateway
from src.api.schemas import (
    ModelConfigResponse,
    ModelConfigTestRequest,
    ModelConfigTestResponse,
    ModelConfigUpdateRequest,
)
from src.kb.providers import OpenAiConfigurationError, OpenAiRequestError

configuration_router = APIRouter(prefix="/api/kb/config/model", tags=["kb-config"])


@configuration_router.get("", response_model=ModelConfigResponse)
def get_model_configuration(model_config_service=Depends(get_model_config_service)) -> ModelConfigResponse:
    return ModelConfigResponse(**model_config_service.get_public_configuration())


@configuration_router.put("", response_model=ModelConfigResponse)
def update_model_configuration(
    payload: ModelConfigUpdateRequest,
    model_config_service=Depends(get_model_config_service),
) -> ModelConfigResponse:
    try:
        result = model_config_service.update_configuration(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ModelConfigResponse(**result)


@configuration_router.post("/test", response_model=ModelConfigTestResponse)
def test_model_configuration(
    payload: ModelConfigTestRequest,
    model_config_service=Depends(get_model_config_service),
    openai_gateway=Depends(get_openai_gateway),
) -> ModelConfigTestResponse:
    try:
        runtime_config = model_config_service.build_runtime_configuration_for_test(payload.model_dump())
        llm_ok, embedding_ok = openai_gateway.test_connection(runtime_config)
        result = model_config_service.build_test_result(
            runtime_config,
            llm_ok=llm_ok,
            embedding_ok=embedding_ok,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OpenAiConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OpenAiRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ModelConfigTestResponse(**result)
