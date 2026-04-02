"""HTTP API Pydantic models."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SystemHealthResponse(BaseModel):
    status: str = "ok"


class SystemCheckItem(BaseModel):
    name: str
    ok: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class SystemReadyResponse(BaseModel):
    status: str
    checks: list[SystemCheckItem] = Field(default_factory=list)


class ApiErrorResponse(BaseModel):
    code: str
    message: str


class ModelConfigResponse(BaseModel):
    provider: str
    base_url: str
    llm_model: str
    embedding_model: str
    has_api_key: bool
    api_key_preview: str | None = None
    api_key_source: str
    reindex_required: bool = False
    notice: str | None = None


class ModelConfigUpdateRequest(BaseModel):
    provider: str
    base_url: str = ""
    llm_model: str
    embedding_model: str
    api_key: str | None = None
    clear_api_key: bool = False


class ModelConfigTestRequest(BaseModel):
    provider: str
    base_url: str = ""
    llm_model: str
    embedding_model: str
    api_key: str | None = None
    use_saved_api_key: bool = False


class ModelConfigTestResponse(BaseModel):
    provider: str
    base_url: str
    llm_model: str
    embedding_model: str
    llm_ok: bool
    embedding_ok: bool
    message: str


class ParagraphItem(BaseModel):
    id: str
    source_id: str
    position: int
    content: str
    knowledge_type: str
    token_count: int
    vector_state: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    render_kind: Literal["text", "row_record", "sheet_summary"] = "text"
    rendered_html: str | None = None
    render_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class SourceItem(BaseModel):
    id: str
    name: str
    source_kind: str
    input_mode: str
    file_type: str | None = None
    storage_path: str | None = None
    strategy: str
    status: str
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class SourceDetailResponse(BaseModel):
    source: SourceItem
    paragraph_count: int
    entity_count: int
    relation_count: int


class SourceParagraphsResponse(BaseModel):
    items: list[ParagraphItem] = Field(default_factory=list)


class GraphNodeItem(BaseModel):
    id: str
    type: str
    label: str
    size: float
    score: float | None = None
    display_label: str | None = None
    kind_label: str | None = None
    source_name: str | None = None
    evidence_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeItem(BaseModel):
    id: str
    source: str
    target: str
    type: str
    label: str
    weight: float
    display_label: str | None = None
    relation_kind_label: str | None = None
    source_name: str | None = None
    evidence_paragraph_id: str | None = None
    is_structural: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    nodes: list[GraphNodeItem] = Field(default_factory=list)
    edges: list[GraphEdgeItem] = Field(default_factory=list)


class GraphNodeDetailResponse(BaseModel):
    node: GraphNodeItem
    source: dict[str, Any] | None = None
    paragraphs: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)


class GraphEdgeDetailResponse(BaseModel):
    edge: GraphEdgeItem
    source: dict[str, Any] | None = None
    paragraph: dict[str, Any] | None = None


class GraphNodeUpdateRequest(BaseModel):
    label: str


class GraphNodeCreateRequest(BaseModel):
    label: str
    description: str = ""
    source_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManualRelationRequest(BaseModel):
    subject_node_id: str
    predicate: str
    object_node_id: str
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManualRelationItem(BaseModel):
    id: str
    subject_node_id: str
    predicate: str
    object_node_id: str
    weight: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class StatusResponse(BaseModel):
    status: str


class SourceUpdateRequest(BaseModel):
    name: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CitationItem(BaseModel):
    paragraph_id: str
    source_id: str
    source_name: str
    excerpt: str
    score: float
    match_reason: str | None = None
    matched_fields: list[str] = Field(default_factory=list)
    source_kind: str | None = None
    worksheet_name: str | None = None
    page_number: int | None = None
    paragraph_position: int | None = None
    winning_lane: str | None = None
    anchor_node_ids: list[str] = Field(default_factory=list)
    preferred_anchor_node_id: str | None = None
    render_kind: Literal["text", "row_record", "sheet_summary"] = "text"
    rendered_html: str | None = None
    render_metadata: dict[str, Any] = Field(default_factory=dict)


class AnswerExecutionItem(BaseModel):
    status: str
    retrieval_mode: str
    model_invoked: bool
    matched_paragraph_count: int
    message: str


class RetrievalTraceLaneItem(BaseModel):
    executed: bool
    skipped_reason: str | None = None
    hit_count: int
    latency_ms: float
    top_paragraph_ids: list[str] = Field(default_factory=list)


class RetrievalTraceItem(BaseModel):
    structured: RetrievalTraceLaneItem
    vector: RetrievalTraceLaneItem
    fusion: RetrievalTraceLaneItem
    ppr: RetrievalTraceLaneItem
    total_ms: float


class ChatSessionCreateRequest(BaseModel):
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessageCreateRequest(BaseModel):
    content: str
    source_ids: list[str] | None = None
    worksheet_names: list[str] | None = None
    top_k: int | None = None


class ChatSessionItem(BaseModel):
    id: str
    title: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    last_message_at: str | None = None


class ChatMessageItem(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    turn_index: int
    citations: list[CitationItem] = Field(default_factory=list)
    execution: AnswerExecutionItem | None = None
    retrieval_trace: RetrievalTraceItem | None = None
    highlighted_node_ids: list[str] = Field(default_factory=list)
    highlighted_edge_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: str
    updated_at: str


class ChatSessionDetailResponse(BaseModel):
    session: ChatSessionItem
    messages: list[ChatMessageItem] = Field(default_factory=list)


class RecordSearchRequest(BaseModel):
    query: str
    source_ids: list[str] = Field(default_factory=list)
    worksheet_names: list[str] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    limit: int = 20


class RecordSearchItem(BaseModel):
    paragraph_id: str
    source_id: str
    source_name: str
    worksheet_name: str
    row_index: int
    content: str
    matched_cells: list[str] = Field(default_factory=list)
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordSearchResponse(BaseModel):
    items: list[RecordSearchItem] = Field(default_factory=list)


class EntitySearchRequest(BaseModel):
    query: str
    limit: int = 20


class EntityItem(BaseModel):
    id: str
    display_name: str
    description: str | None = None
    appearance_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    paragraph_ids: list[str] = Field(default_factory=list)


class EntitySearchResponse(BaseModel):
    items: list[EntityItem] = Field(default_factory=list)


class RelationSearchRequest(BaseModel):
    query: str
    limit: int = 20


class RelationItem(BaseModel):
    id: str
    subject_id: str
    subject_name: str
    predicate: str
    object_id: str
    object_name: str
    confidence: float
    source_paragraph_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationSearchResponse(BaseModel):
    items: list[RelationItem] = Field(default_factory=list)


class SourceSearchRequest(BaseModel):
    query: str
    limit: int = 20


class SourceSearchItem(BaseModel):
    id: str
    name: str
    source_kind: str
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    paragraph_count: int


class SourceSearchResponse(BaseModel):
    items: list[SourceSearchItem] = Field(default_factory=list)


class PasteImportRequest(BaseModel):
    title: str
    content: str
    strategy: str = "auto"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScanImportRequest(BaseModel):
    root_path: str
    glob_pattern: str = "**/*"
    strategy: str = "auto"


class StructuredImportRequest(BaseModel):
    title: str
    payload: dict[str, Any]
    strategy: str = "auto"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImportJobChunkItem(BaseModel):
    id: str
    job_id: str
    file_id: str
    paragraph_id: str | None = None
    chunk_index: int
    chunk_type: str
    status: str
    step: str
    progress: float
    content_preview: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str
    updated_at: str


class ImportJobFileItem(BaseModel):
    id: str
    job_id: str
    source_id: str | None = None
    name: str
    source_kind: str
    input_mode: str
    strategy: str
    status: str
    current_step: str
    progress: float
    total_chunks: int
    completed_chunks: int
    failed_chunks: int
    storage_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    failure_stage: str | None = None
    step_durations: dict[str, float] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    chunks: list[ImportJobChunkItem] = Field(default_factory=list)


class ImportJobItem(BaseModel):
    id: str
    source: str
    input_mode: str
    strategy: str
    status: str
    current_step: str
    progress: float
    total_files: int
    completed_files: int
    failed_files: int
    total_chunks: int
    completed_chunks: int
    failed_chunks: int
    message: str | None = None
    error: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    failure_stage: str | None = None
    step_durations: dict[str, float] = Field(default_factory=dict)
    retry_of: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    updated_at: str
    files: list[ImportJobFileItem] = Field(default_factory=list)


class ImportJobResponse(BaseModel):
    job: ImportJobItem


