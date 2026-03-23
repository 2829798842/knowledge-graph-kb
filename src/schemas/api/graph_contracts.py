"""模块名称：contracts.api.graph_contracts

主要功能：定义图谱节点、边以及手工连边操作相关的接口契约。
"""

from typing import Any

from pydantic import BaseModel, Field


class GraphNodeRead(BaseModel):
    """图节点输出模型。

    Attributes:
        id (str): 节点标识。
        type (str): 节点类型。
        label (str): 节点展示名称。
        score (float | None): 排序得分。
        metadata (dict[str, Any]): 节点附加元数据。
    """

    id: str
    type: str
    label: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeRead(BaseModel):
    """图边输出模型。

    Attributes:
        id (str): 边标识。
        source (str): 源节点标识。
        target (str): 目标节点标识。
        type (str): 边类型。
        weight (float): 边权重。
        metadata (dict[str, Any]): 边附加元数据。
    """

    id: str
    source: str
    target: str
    type: str
    weight: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    """图谱返回模型。

    Attributes:
        nodes (list[GraphNodeRead]): 节点列表。
        edges (list[GraphEdgeRead]): 边列表。
    """

    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]


class CreateEdgeRequest(BaseModel):
    """创建手工边请求模型。

    Attributes:
        source_node_id (str): 源节点标识。
        target_node_id (str): 目标节点标识。
        weight (float): 边权重。
        metadata (dict[str, Any]): 边附加信息。
    """

    source_node_id: str
    target_node_id: str
    weight: float = 1.25
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateEdgeResponse(BaseModel):
    """创建手工边响应模型。

    Attributes:
        edge (GraphEdgeRead): 新建或更新后的边信息。
    """

    edge: GraphEdgeRead
