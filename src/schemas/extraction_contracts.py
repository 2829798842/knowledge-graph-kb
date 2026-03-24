"""定义实体抽取结果中使用的实体、关系与聚合结果契约。
"""


class ExtractedEntity:
    """抽取出的实体。

    Attributes:
        name (str): 实体名称。
        description (str): 实体说明。
    """

    def __init__(self, name: str, description: str = "") -> None:
        """初始化实体对象。

        Args:
            name: 实体名称。
            description: 实体说明。
        """

        self.name: str = name
        self.description: str = description


class ExtractedRelation:
    """抽取出的关系。

    Attributes:
        source (str): 源实体名称。
        target (str): 目标实体名称。
        relation (str): 关系类型描述。
        weight (float): 关系权重。
    """

    def __init__(self, source: str, target: str, relation: str, weight: float = 1.0) -> None:
        """初始化关系对象。

        Args:
            source: 源实体名称。
            target: 目标实体名称。
            relation: 关系描述。
            weight: 关系权重。
        """

        self.source: str = source
        self.target: str = target
        self.relation: str = relation
        self.weight: float = weight


class ExtractionResult:
    """实体关系抽取结果。

    Attributes:
        entities (list[ExtractedEntity]): 抽取到的实体列表。
        relations (list[ExtractedRelation]): 抽取到的关系列表。
    """

    def __init__(
        self,
        entities: list[ExtractedEntity] | None = None,
        relations: list[ExtractedRelation] | None = None,
    ) -> None:
        """初始化抽取结果对象。

        Args:
            entities: 抽取到的实体列表。
            relations: 抽取到的关系列表。
        """

        self.entities: list[ExtractedEntity] = entities or []
        self.relations: list[ExtractedRelation] = relations or []
