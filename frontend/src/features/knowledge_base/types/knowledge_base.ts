/**
 * 模块名称：features/knowledge_base/types/knowledge_base
 * 主要功能：定义知识库前端使用的文档、任务、图谱与查询数据结构。
 */

/**
 * 导入任务状态。
 */
export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';

/**
 * 文档记录。
 */
export interface KnowledgeBaseDocument {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  status: string;
  summary: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/**
 * 任务记录。
 */
export interface KnowledgeBaseJob {
  id: string;
  document_id: string;
  status: JobStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * 图谱节点。
 */
export interface GraphNodeRecord {
  id: string;
  type: string;
  label: string;
  score?: number | null;
  metadata: Record<string, unknown>;
}

/**
 * 图谱边。
 */
export interface GraphEdgeRecord {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
  metadata: Record<string, unknown>;
}

/**
 * 图谱载荷。
 */
export interface GraphPayload {
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
}

/**
 * 引用记录。
 */
export interface CitationRecord {
  chunk_id: string;
  document_id: string;
  node_id: string;
  document_name: string;
  excerpt: string;
  score: number;
}

/**
 * 查询结果。
 */
export interface QueryResult {
  answer: string;
  citations: CitationRecord[];
  ranked_nodes: GraphNodeRecord[];
  ranked_edges: GraphEdgeRecord[];
}
