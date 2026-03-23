"""验证运行期模型配置持久化与连接测试流程。"""

from types import SimpleNamespace

from sqlmodel import select

from src.config import Settings
from src.data import EdgeType, GraphEdge, ModelConfiguration
from src.schemas.api import UpdateModelConfigurationRequest
from src.services import ModelConfigurationService, OpenAiService


def test_model_config_api_reads_defaults_and_persists_encrypted_updates(client, session):
    """The API should expose env defaults, encrypt saved keys, and clear semantic edges on reindex."""

    get_response = client.get("/api/model-config")

    assert get_response.status_code == 200
    assert get_response.json()["provider"] == "openai"
    assert get_response.json()["has_api_key"] is True
    assert get_response.json()["api_key_source"] == "environment"

    session.add(
        GraphEdge(
            source_node_id="entity:left",
            target_node_id="entity:right",
            edge_type=EdgeType.SEMANTIC,
            weight=0.8,
            metadata_json={},
        )
    )
    session.commit()

    update_response = client.put(
        "/api/model-config",
        json={
            "provider": "openrouter",
            "base_url": "",
            "llm_model": "openai/gpt-5.4-mini",
            "embedding_model": "text-embedding-3-small",
            "api_key": "sk-local-12345678",
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["provider"] == "openrouter"
    assert payload["base_url"] == "https://openrouter.ai/api/v1"
    assert payload["llm_model"] == "openai/gpt-5.4-mini"
    assert payload["embedding_model"] == "text-embedding-3-small"
    assert payload["has_api_key"] is True
    assert payload["api_key_source"] == "saved"
    assert payload["api_key_preview"].endswith("5678")
    assert payload["reindex_required"] is True
    assert "嵌入模型已变更" in payload["notice"]

    stored_config = session.get(ModelConfiguration, "default")
    assert stored_config is not None
    assert stored_config.api_key != "sk-local-12345678"
    assert stored_config.api_key.startswith("enc:v1:")
    assert not list(session.exec(select(GraphEdge).where(GraphEdge.edge_type == EdgeType.SEMANTIC)).all())


def test_model_config_test_route_uses_unsaved_payload(client, monkeypatch):
    """The test endpoint should validate the current form values without persisting them."""

    def fake_test_connection(self, runtime_config):  # noqa: ANN001
        assert runtime_config.provider == "custom"
        assert runtime_config.base_url == "https://example.test/v1"
        assert runtime_config.llm_model == "chat-model"
        assert runtime_config.embedding_model == "embed-model"
        assert runtime_config.api_key == "request-key"
        return True, False

    monkeypatch.setattr("src.services.openai_service.OpenAiService.test_connection", fake_test_connection)

    response = client.post(
        "/api/model-config/test",
        json={
            "provider": "custom",
            "base_url": "https://example.test/v1",
            "llm_model": "chat-model",
            "embedding_model": "embed-model",
            "api_key": "request-key",
            "use_saved_api_key": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["llm_ok"] is True
    assert payload["embedding_ok"] is False
    assert "嵌入模型调用失败" in payload["message"]


def test_openai_service_uses_saved_encrypted_runtime_model_configuration(session, monkeypatch):
    """OpenAI service calls should honor the saved provider, key, and model ids."""

    settings = Settings(openai_api_key="env-key")
    model_config_service = ModelConfigurationService(settings)
    model_config_service.update_configuration(
        session,
        UpdateModelConfigurationRequest(
            provider="custom",
            base_url="https://example.test/v1",
            llm_model="chat-model",
            embedding_model="embed-model",
            api_key="saved-key-9999",
        ),
    )

    created_clients: list[SimpleNamespace] = []

    class FakeEmbeddings:
        def __init__(self) -> None:
            self.last_model: str | None = None

        def create(self, *, model: str, input: list[str]):
            self.last_model = model
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2]) for _ in input])

    class FakeChatCompletions:
        def __init__(self) -> None:
            self.last_model: str | None = None

        def create(self, *, model: str, **_: object):
            self.last_model = model
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
            )

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeChatCompletions()

    class FakeOpenAI:
        def __init__(self, *, api_key: str, base_url: str | None = None):
            self.api_key = api_key
            self.base_url = base_url
            self.embeddings = FakeEmbeddings()
            self.chat = FakeChat()
            created_clients.append(
                SimpleNamespace(
                    api_key=api_key,
                    base_url=base_url,
                    embeddings=self.embeddings,
                    chat=self.chat,
                )
            )

    monkeypatch.setattr("src.services.openai_service.OpenAI", FakeOpenAI)

    service = OpenAiService(settings)
    embedding_result = service.embed_texts(["hello world"])
    answer_result = service.answer_query("What happened?", [{"chunk_id": "c1", "document_name": "Doc", "excerpt": "ctx"}])

    assert embedding_result == [[0.1, 0.2]]
    assert answer_result == "answer"
    assert len(created_clients) == 1
    fake_client = created_clients[0]
    assert fake_client.api_key == "saved-key-9999"
    assert fake_client.base_url == "https://example.test/v1"
    assert fake_client.embeddings.last_model == "embed-model"
    assert fake_client.chat.completions.last_model == "chat-model"
