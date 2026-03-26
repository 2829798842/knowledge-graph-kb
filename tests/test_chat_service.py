from pathlib import Path

import pytest

from src.api.schemas import ChatMessageCreateRequest
from src.config import Settings
from src.kb.application.services.chat import ConversationService
from src.kb.database import SQLiteGateway
from src.kb.providers import OpenAiRequestError
from src.kb.storage import ConversationStore


class AnswerServiceStub:
    def __init__(self, *, result: dict | None = None, error: Exception | None = None) -> None:
        self.result = result or {
            "answer": "ok",
            "citations": [],
            "execution": {
                "status": "answered",
                "retrieval_mode": "structured",
                "model_invoked": True,
                "matched_paragraph_count": 1,
                "message": "ok",
            },
            "retrieval_trace": {
                "structured": {
                    "executed": True,
                    "skipped_reason": None,
                    "hit_count": 1,
                    "latency_ms": 1.0,
                    "top_paragraph_ids": [],
                },
                "vector": {
                    "executed": False,
                    "skipped_reason": "structured_short_circuit",
                    "hit_count": 0,
                    "latency_ms": 0.0,
                    "top_paragraph_ids": [],
                },
                "fusion": {
                    "executed": False,
                    "skipped_reason": "structured_short_circuit",
                    "hit_count": 0,
                    "latency_ms": 0.0,
                    "top_paragraph_ids": [],
                },
                "ppr": {
                    "executed": False,
                    "skipped_reason": "structured_short_circuit",
                    "hit_count": 0,
                    "latency_ms": 0.0,
                    "top_paragraph_ids": [],
                },
                "total_ms": 1.0,
            },
            "highlighted_node_ids": [],
            "highlighted_edge_ids": [],
        }
        self.error = error

    def answer(self, **_: object) -> dict:
        if self.error is not None:
            raise self.error
        return self.result

    def hydrate_citations(self, citations: list[dict]) -> list[dict]:
        return citations


@pytest.fixture
def conversation_dependencies(tmp_path: Path) -> tuple[ConversationStore, Settings]:
    settings = Settings(kb_data_dir=str(tmp_path / "data"))
    gateway = SQLiteGateway(tmp_path / "kb.sqlite3")
    gateway.initialize()
    store = ConversationStore(gateway)
    return store, settings


def test_chat_message_request_keeps_scope_optional() -> None:
    request = ChatMessageCreateRequest.model_validate({"content": "hello"})
    assert request.source_ids is None
    assert request.worksheet_names is None


def test_post_user_message_preserves_session_metadata_when_scope_omitted(
    conversation_dependencies: tuple[ConversationStore, Settings],
) -> None:
    store, settings = conversation_dependencies
    service = ConversationService(
        settings=settings,
        store=store,
        answer_service=AnswerServiceStub(),
    )
    session = store.create_session(title="新对话", metadata={"source_ids": ["source-a"], "worksheet_names": ["Sheet1"]})

    updated_session = service.post_user_message(session_id=str(session["id"]), content="帮我总结一下")

    assert updated_session["metadata"]["source_ids"] == ["source-a"]
    assert updated_session["metadata"]["worksheet_names"] == ["Sheet1"]
    assert updated_session["title"] == "帮我总结一下"


def test_post_user_message_persists_assistant_error_on_failure(
    conversation_dependencies: tuple[ConversationStore, Settings],
) -> None:
    store, settings = conversation_dependencies
    service = ConversationService(
        settings=settings,
        store=store,
        answer_service=AnswerServiceStub(error=OpenAiRequestError("模型请求失败", status_code=503)),
    )
    session = store.create_session(title="新对话", metadata={})

    with pytest.raises(OpenAiRequestError):
        service.post_user_message(session_id=str(session["id"]), content="这次会失败吗")

    messages = store.list_messages(str(session["id"]))
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "模型请求失败"
    assert messages[1]["error"] == "模型请求失败"
    assert messages[1]["execution"]["status"] == "failed"
