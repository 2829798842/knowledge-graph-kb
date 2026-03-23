"""负责模型配置的持久化与运行期解析。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from sqlmodel import Session, select

from src.config import Settings
from src.data import EdgeType, GraphEdge, ModelConfiguration
from src.schemas.api import (
    ModelConfigurationRead,
    ModelConfigurationTestResult,
    TestModelConfigurationRequest,
    UpdateModelConfigurationRequest,
)
from src.services.vector_store_service import FaissVectorStore
from src.utils.secret_utils import LocalSecretCipher

DEFAULT_MODEL_CONFIG_ID: Final[str] = "default"
MODEL_PROVIDER_BASE_URLS: Final[dict[str, str]] = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "custom": "",
}
REINDEX_NOTICE: Final[str] = "嵌入模型已变更，现有向量索引和语义边已清空，请重新导入文档以重建检索。"


@dataclass(frozen=True)
class RuntimeModelConfiguration:
    """模型调用时使用的生效运行期配置。"""

    provider: str
    base_url: str
    api_key: str
    llm_model: str
    embedding_model: str
    api_key_source: str


class ModelConfigurationService:
    """管理持久化配置，并推导可安全使用的运行期模型配置。"""

    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self.secret_cipher: LocalSecretCipher = LocalSecretCipher(settings)

    def get_public_configuration(
        self,
        session: Session,
        *,
        reindex_required: bool = False,
        notice: str | None = None,
    ) -> ModelConfigurationRead:
        """返回当前可安全暴露给前端的配置结果。"""

        runtime_config: RuntimeModelConfiguration = self.resolve_runtime_configuration(session)
        return ModelConfigurationRead(
            provider=runtime_config.provider,
            base_url=runtime_config.base_url,
            llm_model=runtime_config.llm_model,
            embedding_model=runtime_config.embedding_model,
            has_api_key=bool(runtime_config.api_key),
            api_key_preview=self._mask_api_key(runtime_config.api_key) if runtime_config.api_key else None,
            api_key_source=runtime_config.api_key_source,
            reindex_required=reindex_required,
            notice=notice,
        )

    def update_configuration(
        self,
        session: Session,
        payload: UpdateModelConfigurationRequest,
    ) -> ModelConfigurationRead:
        """持久化运行期模型配置，并返回其对前端可见的视图。"""

        previous_config: RuntimeModelConfiguration = self.resolve_runtime_configuration(session)
        provider: str = self._normalize_provider(payload.provider)
        base_url: str = self._normalize_base_url(provider, payload.base_url)
        llm_model: str = self._require_non_empty(payload.llm_model, "通用模型名称不能为空。")
        embedding_model: str = self._require_non_empty(payload.embedding_model, "嵌入模型名称不能为空。")

        model_config: ModelConfiguration = self._get_or_create_model_config(session)
        model_config.provider = provider
        model_config.base_url = base_url
        model_config.llm_model = llm_model
        model_config.embedding_model = embedding_model

        if payload.clear_api_key:
            model_config.api_key = None
        elif payload.api_key is not None:
            cleaned_api_key: str = payload.api_key.strip()
            model_config.api_key = self.secret_cipher.encrypt(cleaned_api_key) if cleaned_api_key else None

        session.add(model_config)
        session.commit()
        session.refresh(model_config)

        reindex_required: bool = previous_config.embedding_model != embedding_model
        notice: str | None = None
        if reindex_required:
            self._reset_embedding_artifacts(session)
            notice = REINDEX_NOTICE

        return self.get_public_configuration(session, reindex_required=reindex_required, notice=notice)

    def resolve_runtime_configuration(self, session: Session) -> RuntimeModelConfiguration:
        """合并持久化配置与环境默认值，并在需要时解密密钥。"""

        model_config: ModelConfiguration | None = session.get(ModelConfiguration, DEFAULT_MODEL_CONFIG_ID)
        provider: str = self._normalize_provider(
            model_config.provider if model_config is not None else self.settings.model_provider,
        )
        base_url: str = self._normalize_base_url(
            provider,
            model_config.base_url if model_config is not None else self.settings.model_base_url,
        )
        saved_api_key: str = self._resolve_saved_api_key(model_config.api_key if model_config is not None else None)
        env_api_key: str = self.settings.openai_api_key.strip()
        api_key: str = saved_api_key or env_api_key
        api_key_source: str = "saved" if saved_api_key else ("environment" if env_api_key else "none")
        llm_model: str = (
            model_config.llm_model.strip()
            if model_config is not None and model_config.llm_model.strip()
            else self.settings.openai_llm_model
        )
        embedding_model: str = (
            model_config.embedding_model.strip()
            if model_config is not None and model_config.embedding_model.strip()
            else self.settings.openai_embed_model
        )

        return RuntimeModelConfiguration(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            llm_model=llm_model,
            embedding_model=embedding_model,
            api_key_source=api_key_source,
        )

    def build_runtime_configuration_for_test(
        self,
        session: Session,
        payload: TestModelConfigurationRequest,
    ) -> RuntimeModelConfiguration:
        """构建仅用于连通性测试、但不会保存的运行期配置。"""

        current_runtime_config: RuntimeModelConfiguration = self.resolve_runtime_configuration(session)
        provider: str = self._normalize_provider(payload.provider)
        base_url: str = self._normalize_base_url(provider, payload.base_url)
        llm_model: str = self._require_non_empty(payload.llm_model, "通用模型名称不能为空。")
        embedding_model: str = self._require_non_empty(payload.embedding_model, "嵌入模型名称不能为空。")

        explicit_api_key: str = payload.api_key.strip() if payload.api_key else ""
        api_key: str = explicit_api_key or (current_runtime_config.api_key if payload.use_saved_api_key else "")
        api_key_source: str = "request" if explicit_api_key else current_runtime_config.api_key_source
        if not api_key:
            raise ValueError("请先填写 API Key，或保留已保存的可用密钥。")

        return RuntimeModelConfiguration(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            llm_model=llm_model,
            embedding_model=embedding_model,
            api_key_source=api_key_source,
        )

    def build_test_result(
        self,
        runtime_config: RuntimeModelConfiguration,
        *,
        llm_ok: bool,
        embedding_ok: bool,
    ) -> ModelConfigurationTestResult:
        """构造适合前端展示的连接测试结果。"""

        message: str = "当前配置可正常访问通用模型和嵌入模型。"
        if not llm_ok and not embedding_ok:
            message = "当前配置无法访问通用模型和嵌入模型，请检查供应商、Base URL、模型名和 API Key。"
        elif not llm_ok:
            message = "嵌入模型可用，但通用模型调用失败，请检查通用模型名称或供应商兼容性。"
        elif not embedding_ok:
            message = "通用模型可用，但嵌入模型调用失败，请检查嵌入模型名称或供应商兼容性。"

        return ModelConfigurationTestResult(
            provider=runtime_config.provider,
            base_url=runtime_config.base_url,
            llm_model=runtime_config.llm_model,
            embedding_model=runtime_config.embedding_model,
            llm_ok=llm_ok,
            embedding_ok=embedding_ok,
            message=message,
        )

    def _get_or_create_model_config(self, session: Session) -> ModelConfiguration:
        """读取单例形式保存的模型配置记录。"""

        model_config: ModelConfiguration | None = session.get(ModelConfiguration, DEFAULT_MODEL_CONFIG_ID)
        if model_config is None:
            model_config = ModelConfiguration(id=DEFAULT_MODEL_CONFIG_ID)
        return model_config

    def _normalize_provider(self, raw_provider: str) -> str:
        """规整并校验供应商名称。"""

        provider: str = raw_provider.strip().lower()
        if provider not in MODEL_PROVIDER_BASE_URLS:
            raise ValueError("暂不支持该 API 供应商，请选择预设供应商或使用自定义模式。")
        return provider

    def _normalize_base_url(self, provider: str, raw_base_url: str) -> str:
        """规整供应商的 Base URL。"""

        base_url: str = raw_base_url.strip().rstrip("/")
        if provider == "custom":
            if not base_url:
                raise ValueError("自定义供应商必须填写 Base URL。")
            return base_url
        return base_url or MODEL_PROVIDER_BASE_URLS[provider]

    def _require_non_empty(self, value: str, message: str) -> str:
        """校验必填文本字段。"""

        cleaned_value: str = value.strip()
        if not cleaned_value:
            raise ValueError(message)
        return cleaned_value

    def _resolve_saved_api_key(self, stored_value: str | None) -> str:
        """解析已保存的 API Key，并兼容旧版明文值。"""

        if not stored_value:
            return ""
        return self.secret_cipher.decrypt(stored_value).strip()

    def _reset_embedding_artifacts(self, session: Session) -> None:
        """当嵌入模型变更后，清空 FAISS 数据与语义边。"""

        vector_store = FaissVectorStore(self.settings)
        vector_store.reset()

        semantic_edges: list[GraphEdge] = list(
            session.exec(select(GraphEdge).where(GraphEdge.edge_type == EdgeType.SEMANTIC)).all()
        )
        for edge in semantic_edges:
            session.delete(edge)
        session.commit()

    def _mask_api_key(self, api_key: str) -> str:
        """返回可安全展示的密钥预览文本。"""

        trimmed_key: str = api_key.strip()
        if len(trimmed_key) <= 8:
            return f"{trimmed_key[:2]}***"
        return f"{trimmed_key[:4]}...{trimmed_key[-4:]}"
