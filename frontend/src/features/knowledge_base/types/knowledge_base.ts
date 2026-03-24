/**
 * 模块名称：features/knowledge_base/types/knowledge_base
 * 主要功能：定义知识库工作台共享的前端数据结构。
 */

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type DocumentStatus = 'queued' | 'processing' | 'ready' | 'failed';
export type ApiKeySource = 'saved' | 'environment' | 'none';
export type ModelProvider = 'openai' | 'openrouter' | 'siliconflow' | 'custom';

export interface KnowledgeBaseDocument {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  status: DocumentStatus;
  summary: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseJob {
  id: string;
  document_id: string;
  status: JobStatus;
  progress_percent: number;
  stage: string;
  stage_current: number;
  stage_total: number;
  stage_unit: string | null;
  status_message: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface GraphNodeRecord {
  id: string;
  type: string;
  label: string;
  score?: number | null;
  metadata: Record<string, unknown>;
}

export interface GraphEdgeRecord {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
  metadata: Record<string, unknown>;
}

export interface GraphPayload {
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
}

export interface CitationRecord {
  chunk_id: string;
  document_id: string;
  node_id: string;
  document_name: string;
  excerpt: string;
  score: number;
}

export interface QueryResult {
  answer: string;
  citations: CitationRecord[];
  ranked_nodes: GraphNodeRecord[];
  ranked_edges: GraphEdgeRecord[];
}

export interface ModelConfiguration {
  provider: ModelProvider;
  base_url: string;
  llm_model: string;
  embedding_model: string;
  has_api_key: boolean;
  api_key_preview: string | null;
  api_key_source: ApiKeySource;
  reindex_required: boolean;
  notice: string | null;
}

export interface ModelConfigurationUpdateRequest {
  provider: ModelProvider;
  base_url: string;
  llm_model: string;
  embedding_model: string;
  api_key?: string;
  clear_api_key?: boolean;
}

export interface ModelConfigurationTestRequest {
  provider: ModelProvider;
  base_url: string;
  llm_model: string;
  embedding_model: string;
  api_key?: string;
  use_saved_api_key?: boolean;
}

export interface ModelConfigurationTestResult {
  provider: ModelProvider;
  base_url: string;
  llm_model: string;
  embedding_model: string;
  llm_ok: boolean;
  embedding_ok: boolean;
  message: string;
}
