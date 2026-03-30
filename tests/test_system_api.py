from fastapi.testclient import TestClient


def test_system_health_and_ready(client: TestClient) -> None:
    health_response = client.get("/api/system/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    ready_response = client.get("/api/system/ready")
    assert ready_response.status_code == 200

    payload = ready_response.json()
    assert payload["status"] == "ready"
    check_names = {item["name"] for item in payload["checks"]}
    assert check_names == {"database", "vector_index", "model_config", "frontend_dist"}
    assert all(item["ok"] for item in payload["checks"])
