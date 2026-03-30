from pathlib import Path

from fastapi.testclient import TestClient

from src.config import Settings
from src.kb.application.services import restore_backup


def import_sample_source(client: TestClient) -> dict:
    response = client.post(
        "/api/kb/imports/paste",
        json={
            "title": "Alpha Notes",
            "content": "Alpha 依赖 Beta。Beta 为 Alpha 提供数据支持。",
            "strategy": "auto",
            "metadata": {"filename": "alpha.txt"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["job"]


def test_import_job_source_update_graph_create_and_backup(client: TestClient, tmp_path: Path) -> None:
    job = import_sample_source(client)

    assert job["status"] in {"completed", "partial"}
    assert job["failure_stage"] is None
    assert isinstance(job["step_durations"], dict)
    assert job["stats"]["paragraph_count"] >= 1
    assert len(job["files"]) == 1
    assert job["files"][0]["stats"]["paragraph_count"] >= 1

    sources_response = client.get("/api/kb/sources")
    assert sources_response.status_code == 200
    sources = sources_response.json()
    assert len(sources) == 1
    source_id = sources[0]["id"]

    update_response = client.put(
        f"/api/kb/sources/{source_id}",
        json={"name": "Alpha Source", "summary": "更新后的摘要", "metadata": {"owner": "qa"}},
    )
    assert update_response.status_code == 200
    updated_source = update_response.json()
    assert updated_source["name"] == "Alpha Source"
    assert updated_source["summary"] == "更新后的摘要"
    assert updated_source["metadata"]["owner"] == "qa"

    create_node_response = client.post(
        "/api/kb/graph/nodes",
        json={"label": "Manual Entity", "description": "人工创建的实体", "metadata": {"scope": "test"}},
    )
    assert create_node_response.status_code == 200
    node = create_node_response.json()
    assert node["id"].startswith("entity:")
    assert node["type"] == "entity"
    assert node["label"] == "Manual Entity"

    graph_response = client.get("/api/kb/graph")
    assert graph_response.status_code == 200
    graph = graph_response.json()
    assert any(item["id"] == node["id"] for item in graph["nodes"])
    assert any(item["id"].startswith("source:") for item in graph["nodes"])

    maintenance = client.app.state.kb_container.maintenance_service
    doctor_result = maintenance.doctor()
    assert doctor_result["status"] == "ok"

    backup_result = maintenance.backup(output_dir=tmp_path / "backup")
    backup_dir = Path(backup_result["backup_dir"])
    assert backup_dir.exists()
    assert (backup_dir / "manifest.json").exists()

    restore_settings = Settings(
        kb_data_dir=str(tmp_path / "restored-kb"),
        frontend_dist_dir=str(client.app.state.kb_container.settings.resolved_frontend_dist_dir),
        openai_api_key="test-api-key",
    )
    restore_result = restore_backup(settings=restore_settings, backup_dir=backup_dir, force=True)
    assert restore_result["status"] == "ok"
    assert (restore_settings.resolved_kb_db_path).exists()
