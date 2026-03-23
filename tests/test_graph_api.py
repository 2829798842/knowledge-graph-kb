"""模块名称：tests.test_graph_api

主要功能：验证图谱接口中的手工边创建、查询与删除流程。
"""

from src.data import GraphNode, NodeType


def test_manual_edge_crud_and_graph_response(client, session):
    """验证手工边的增删改查结果会反映到图谱接口返回中。"""

    left = GraphNode(id="entity:left", node_type=NodeType.ENTITY, label="Left node", ref_id="entity:left", metadata_json={})
    right = GraphNode(id="entity:right", node_type=NodeType.ENTITY, label="Right node", ref_id="entity:right", metadata_json={})
    session.add(left)
    session.add(right)
    session.commit()

    create_response = client.post(
        "/api/edges",
        json={
            "source_node_id": left.id,
            "target_node_id": right.id,
            "weight": 1.3,
            "metadata": {"test": True},
        },
    )
    assert create_response.status_code == 200
    edge_payload = create_response.json()["edge"]
    assert edge_payload["type"] == "manual"

    graph_response = client.get("/api/graph")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert {node["id"] for node in graph_payload["nodes"]} >= {left.id, right.id}
    assert any(edge["id"] == edge_payload["id"] for edge in graph_payload["edges"])

    delete_response = client.delete(f"/api/edges/{edge_payload['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"
