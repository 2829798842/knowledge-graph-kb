"""模型配置应用服务。"""

from typing import Final

from src.config import Settings
from src.kb.common import RuntimeModelConfiguration
from src.kb.storage import ModelConfigStore, VectorIndex
from src.utils.logger import get_logger
from src.utils.secret import LocalSecretCipher, SecretEncryptionError

MODEL_PROVIDER_BASE_URLS: Final[dict[str, str]] = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "custom": "",
}
REINDEX_NOTICE: Final[str] = "嵌入模型已变更，现有向量索引已清空，请重新导入内容。"
INVALID_SAVED_API_KEY_NOTICE: Final[str] = "已保存的 API Key 无法解密，请重新保存一次模型配置。"

logger = get_logger(__name__)


class ModelConfigService:
    """管理持久化模型配置与运行时配置。"""

    def __init__(
        self,
        *,
        settings: Settings,
        store: ModelConfigStore,
        vector_index: VectorIndex,
    ) -> None:
        """初始化模型配置服务。"""

        self.settings = settings
        self.store = store
        self.vector = vector_index
        self.secret_cipher = LocalSecretCipher(settings)

    def resolve_runtime_configuration(self) -> RuntimeModelConfiguration:
        """解析当前生效的运行时配置。"""

        runtime_config, _ = self._resolve_runtime_configuration_with_notice()
        return runtime_config

    def _resolve_runtime_configuration_with_notice(self) -> tuple[RuntimeModelConfiguration, str | None]:
        """解析运行时配置，并返回可能的提示信息。"""

        model_config = self.store.get()
        provider = self._normalize_provider(
            str(model_config["provider"]) if model_config is not None else self.settings.model_provider,
        )
        base_url = self._normalize_base_url(
            provider,
            str(model_config["base_url"]) if model_config is not None else self.settings.model_base_url,
        )

        saved_api_key = ""
        notice: str | None = None
        if model_config is not None and model_config.get("api_key"):
            try:
                saved_api_key = self._resolve_saved_api_key(str(model_config["api_key"]))
            except SecretEncryptionError:
                saved_api_key = ""
                notice = INVALID_SAVED_API_KEY_NOTICE
                logger.warning("已保存的 API Key 无法解密，系统将回退到环境变量中的密钥。")

        env_api_key = self.settings.openai_api_key.strip()
        api_key = saved_api_key or env_api_key
        api_key_source = "saved" if saved_api_key else ("environment" if env_api_key else "none")

        llm_model = (
            str(model_config["llm_model"]).strip()
            if model_config is not None and str(model_config.get("llm_model") or "").strip()
            else self.settings.openai_llm_model
        )
        embedding_model = (
            str(model_config["embedding_model"]).strip()
            if model_config is not None and str(model_config.get("embedding_model") or "").strip()
            else self.settings.openai_embed_model
        )

        return (
            RuntimeModelConfiguration(
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                llm_model=llm_model,
                embedding_model=embedding_model,
                api_key_source=api_key_source,
            ),
            notice,
        )

    def get_public_configuration(self, *, reindex_required: bool = False, notice: str | None = None) -> dict[str, object]:
        """返回可安全暴露给前端的配置视图。"""

        runtime_config, runtime_notice = self._resolve_runtime_configuration_with_notice()
        combined_notice = notice or runtime_notice
        return {
            "provider": runtime_config.provider,
            "base_url": runtime_config.base_url,
            "llm_model": runtime_config.llm_model,
            "embedding_model": runtime_config.embedding_model,
            "has_api_key": bool(runtime_config.api_key),
            "api_key_preview": self._mask_api_key(runtime_config.api_key) if runtime_config.api_key else None,
            "api_key_source": runtime_config.api_key_source,
            "reindex_required": reindex_required,
            "notice": combined_notice,
        }

    def update_configuration(self, payload: dict[str, object]) -> dict[str, object]:
        """更新模型配置，并在嵌入模型变更时重置向量索引。"""

        previous = self.resolve_runtime_configuration()

        provider = self._normalize_provider(str(payload.get("provider") or ""))
        base_url = self._normalize_base_url(provider, str(payload.get("base_url") or ""))
        llm_model = self._require_non_empty(str(payload.get("llm_model") or ""), "通用模型名称不能为空。")
        embedding_model = self._require_non_empty(str(payload.get("embedding_model") or ""), "嵌入模型名称不能为空。")

        existing = self.store.get()
        saved_api_key = str(existing["api_key"]) if existing and existing.get("api_key") else None

        clear_api_key = bool(payload.get("clear_api_key"))
        raw_api_key = payload.get("api_key")
        encrypted_api_key = saved_api_key

        if clear_api_key:
            encrypted_api_key = None
        elif raw_api_key is not None:
            cleaned_api_key = str(raw_api_key).strip()
            encrypted_api_key = self.secret_cipher.encrypt(cleaned_api_key) if cleaned_api_key else None

        logger.info(
            "开始更新模型配置：provider=%s llm_model=%s embedding_model=%s clear_api_key=%s provided_api_key=%s",
            provider,
            llm_model,
            embedding_model,
            clear_api_key,
            raw_api_key is not None,
        )
        self.store.upsert(
            provider=provider,
            base_url=base_url,
            llm_model=llm_model,
            embedding_model=embedding_model,
            api_key=encrypted_api_key,
        )

        reindex_required = previous.embedding_model != embedding_model
        notice = None
        if reindex_required:
            self.vector.reset()
            notice = REINDEX_NOTICE
            logger.info(
                "嵌入模型发生变化，已重置向量索引：previous=%s current=%s",
                previous.embedding_model,
                embedding_model,
            )

        logger.info(
            "模型配置更新完成：provider=%s llm_model=%s embedding_model=%s reindex_required=%s",
            provider,
            llm_model,
            embedding_model,
            reindex_required,
        )
        return self.get_public_configuration(reindex_required=reindex_required, notice=notice)

    def build_runtime_configuration_for_test(self, payload: dict[str, object]) -> RuntimeModelConfiguration:
        """基于测试请求构造临时运行时配置。"""

        current = self.resolve_runtime_configuration()
        provider = self._normalize_provider(str(payload.get("provider") or ""))
        base_url = self._normalize_base_url(provider, str(payload.get("base_url") or ""))
        llm_model = self._require_non_empty(str(payload.get("llm_model") or ""), "通用模型名称不能为空。")
        embedding_model = self._require_non_empty(str(payload.get("embedding_model") or ""), "嵌入模型名称不能为空。")

        explicit_api_key = str(payload.get("api_key") or "").strip()
        use_saved_api_key = bool(payload.get("use_saved_api_key"))
        api_key = explicit_api_key or (current.api_key if use_saved_api_key else "")
        api_key_source = "request" if explicit_api_key else current.api_key_source
        if not api_key:
            raise ValueError("请先填写 API Key，或保留已保存的可用密钥。")

        logger.info(
            "构造模型测试配置：provider=%s llm_model=%s embedding_model=%s api_key_source=%s",
            provider,
            llm_model,
            embedding_model,
            api_key_source,
        )
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
    ) -> dict[str, object]:
        """构造模型连通性测试结果。"""

        message = "当前配置可访问通用模型和嵌入模型。"
        if not llm_ok and not embedding_ok:
            message = "当前配置无法访问通用模型和嵌入模型，请检查供应商、Base URL、模型名称与 API Key。"
        elif not llm_ok:
            message = "嵌入模型可用，但通用模型请求失败。"
        elif not embedding_ok:
            message = "通用模型可用，但嵌入模型请求失败。"
        return {
            "provider": runtime_config.provider,
            "base_url": runtime_config.base_url,
            "llm_model": runtime_config.llm_model,
            "embedding_model": runtime_config.embedding_model,
            "llm_ok": llm_ok,
            "embedding_ok": embedding_ok,
            "message": message,
        }

    def embedding_model_signature(self) -> str:
        """返回当前嵌入模型签名。"""

        runtime_config = self.resolve_runtime_configuration()
        return f"{runtime_config.provider}:{runtime_config.embedding_model}"

    def _normalize_provider(self, raw_provider: str) -> str:
        """规范化并校验提供商标识。"""

        provider = raw_provider.strip().lower()
        if provider not in MODEL_PROVIDER_BASE_URLS:
            raise ValueError("暂不支持该 API 提供商。")
        return provider

    def _normalize_base_url(self, provider: str, raw_base_url: str) -> str:
        """根据提供商归一化 Base URL。"""

        base_url = raw_base_url.strip().rstrip("/")
        if provider == "custom":
            if not base_url:
                raise ValueError("自定义提供商必须填写 Base URL。")
            return base_url
        return base_url or MODEL_PROVIDER_BASE_URLS[provider]

    def _require_non_empty(self, value: str, message: str) -> str:
        """校验字符串非空。"""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError(message)
        return cleaned

    def _resolve_saved_api_key(self, stored_value: str | None) -> str:
        """解密持久化 API Key。"""

        if not stored_value:
            return ""
        return self.secret_cipher.decrypt(stored_value).strip()

    def _mask_api_key(self, api_key: str) -> str:
        """对 API Key 做脱敏展示。"""

        trimmed = api_key.strip()
        if len(trimmed) <= 8:
            return f"{trimmed[:2]}***"
        return f"{trimmed[:4]}...{trimmed[-4:]}"
