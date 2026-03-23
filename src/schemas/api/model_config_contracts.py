"""运行期模型配置 API 的模式定义。"""

from pydantic import BaseModel


class ModelConfigurationRead(BaseModel):
    """可安全返回给前端的模型配置载荷。"""

    provider: str
    base_url: str
    llm_model: str
    embedding_model: str
    has_api_key: bool
    api_key_preview: str | None = None
    api_key_source: str
    reindex_required: bool = False
    notice: str | None = None


class UpdateModelConfigurationRequest(BaseModel):
    """用于保存运行期模型配置的请求载荷。"""

    provider: str
    base_url: str = ""
    llm_model: str
    embedding_model: str
    api_key: str | None = None
    clear_api_key: bool = False


class TestModelConfigurationRequest(BaseModel):
    """用于校验供应商、模型和 API Key 且不会保存的请求载荷。"""

    provider: str
    base_url: str = ""
    llm_model: str
    embedding_model: str
    api_key: str | None = None
    use_saved_api_key: bool = True


class ModelConfigurationTestResult(BaseModel):
    """返回给前端的连接测试结果。"""

    provider: str
    base_url: str
    llm_model: str
    embedding_model: str
    llm_ok: bool
    embedding_ok: bool
    message: str
