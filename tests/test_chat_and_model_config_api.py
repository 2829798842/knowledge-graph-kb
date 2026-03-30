from fastapi.testclient import TestClient


def _import_source_for_chat(client: TestClient) -> None:
    response = client.post(
        "/api/kb/imports/paste",
        json={
            "title": "Chat Source",
            "content": "Alpha 项目由 Beta 团队负责推进，并在本周完成交付。",
            "strategy": "auto",
            "metadata": {"filename": "chat.txt"},
        },
    )
    assert response.status_code == 200, response.text


def test_model_config_routes(client: TestClient) -> None:
    get_response = client.get("/api/kb/config/model")
    assert get_response.status_code == 200
    current_config = get_response.json()
    assert current_config["has_api_key"] is True

    update_response = client.put(
        "/api/kb/config/model",
        json={
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "llm_model": "gpt-5.4-mini",
            "embedding_model": "text-embedding-3-large",
            "api_key": "saved-key",
            "clear_api_key": False,
        },
    )
    assert update_response.status_code == 200
    updated_config = update_response.json()
    assert updated_config["provider"] == "openai"
    assert updated_config["has_api_key"] is True

    test_response = client.post(
        "/api/kb/config/model/test",
        json={
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "llm_model": "gpt-5.4-mini",
            "embedding_model": "text-embedding-3-large",
            "use_saved_api_key": True,
        },
    )
    assert test_response.status_code == 200
    payload = test_response.json()
    assert payload["llm_ok"] is True
    assert payload["embedding_ok"] is True


def test_chat_message_returns_sources_and_diagnostics(client: TestClient) -> None:
    _import_source_for_chat(client)

    create_session_response = client.post(
        "/api/kb/chat/sessions",
        json={"title": "测试会话", "metadata": {}},
    )
    assert create_session_response.status_code == 200
    session = create_session_response.json()

    message_response = client.post(
        f"/api/kb/chat/sessions/{session['id']}/messages",
        json={"content": "Alpha 项目是谁负责的？", "top_k": 4},
    )
    assert message_response.status_code == 200, message_response.text
    detail = message_response.json()
    assert detail["session"]["id"] == session["id"]
    assert len(detail["messages"]) >= 2

    assistant_messages = [message for message in detail["messages"] if message["role"] == "assistant"]
    assert assistant_messages
    latest_assistant = assistant_messages[-1]
    assert latest_assistant["citations"]
    assert latest_assistant["execution"]["matched_paragraph_count"] >= 1
    assert "retrieval_trace" in latest_assistant
