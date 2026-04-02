from fastapi.testclient import TestClient


def import_named_source(client: TestClient, *, title: str, content: str) -> dict:
    response = client.post(
        "/api/kb/imports/paste",
        json={
            "title": title,
            "content": content,
            "strategy": "auto",
            "metadata": {"filename": f"{title}.txt"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["job"]


def test_manual_entity_respects_single_source_scope(client: TestClient) -> None:
    import_named_source(client, title="Scope One", content="Alpha 支持 Beta。")
    import_named_source(client, title="Scope Two", content="Gamma 影响 Delta。")

    sources_response = client.get("/api/kb/sources")
    assert sources_response.status_code == 200, sources_response.text
    source_rows = {item["name"]: item["id"] for item in sources_response.json()}

    source_one_id = source_rows["Scope One"]
    source_two_id = source_rows["Scope Two"]

    create_node_response = client.post(
        "/api/kb/graph/nodes",
        json={
            "label": "Scoped Manual Entity",
            "description": "Bound to Scope One",
            "source_id": source_one_id,
            "metadata": {"scope": "manual-test"},
        },
    )
    assert create_node_response.status_code == 200, create_node_response.text
    node = create_node_response.json()

    graph_one = client.get("/api/kb/graph", params=[("source_ids", source_one_id)]).json()
    graph_two = client.get("/api/kb/graph", params=[("source_ids", source_two_id)]).json()

    assert any(item["id"] == node["id"] for item in graph_one["nodes"])
    assert all(item["id"] != node["id"] for item in graph_two["nodes"])


def test_manual_relation_rejects_cross_source_scope(client: TestClient) -> None:
    import_named_source(client, title="Scope One", content="Alpha 支持 Beta。")
    import_named_source(client, title="Scope Two", content="Gamma 影响 Delta。")

    source_rows = {item["name"]: item["id"] for item in client.get("/api/kb/sources").json()}
    source_one_id = source_rows["Scope One"]
    source_two_id = source_rows["Scope Two"]

    node_one = client.post(
        "/api/kb/graph/nodes",
        json={"label": "Scoped A", "source_id": source_one_id, "metadata": {"scope": "one"}},
    ).json()
    node_two = client.post(
        "/api/kb/graph/nodes",
        json={"label": "Scoped B", "source_id": source_two_id, "metadata": {"scope": "two"}},
    ).json()

    relation_response = client.post(
        "/api/kb/graph/manual-relations",
        json={
            "subject_node_id": node_one["id"],
            "predicate": "关联",
            "object_node_id": node_two["id"],
            "weight": 1.0,
            "metadata": {},
        },
    )

    assert relation_response.status_code == 400, relation_response.text
    assert "同一来源范围" in relation_response.text


def test_delete_source_removes_scoped_manual_entities(client: TestClient) -> None:
    import_named_source(client, title="Scope One", content="Alpha 支持 Beta。")

    source_rows = {item["name"]: item["id"] for item in client.get("/api/kb/sources").json()}
    source_one_id = source_rows["Scope One"]

    node_one = client.post(
        "/api/kb/graph/nodes",
        json={"label": "Scoped A", "source_id": source_one_id, "metadata": {"scope": "one"}},
    ).json()
    node_two = client.post(
        "/api/kb/graph/nodes",
        json={"label": "Scoped B", "source_id": source_one_id, "metadata": {"scope": "one"}},
    ).json()

    relation_response = client.post(
        "/api/kb/graph/manual-relations",
        json={
            "subject_node_id": node_one["id"],
            "predicate": "关联",
            "object_node_id": node_two["id"],
            "weight": 1.0,
            "metadata": {},
        },
    )
    assert relation_response.status_code == 200, relation_response.text

    delete_response = client.delete(f"/api/kb/sources/{source_one_id}")
    assert delete_response.status_code == 200, delete_response.text

    graph = client.get("/api/kb/graph").json()
    node_ids = {item["id"] for item in graph["nodes"]}
    edge_ids = {item["id"] for item in graph["edges"]}

    assert node_one["id"] not in node_ids
    assert node_two["id"] not in node_ids
    assert relation_response.json()["id"] not in edge_ids
