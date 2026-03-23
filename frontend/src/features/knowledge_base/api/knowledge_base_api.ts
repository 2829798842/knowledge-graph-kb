/**
 * 模块名称：features/knowledge_base/api/knowledge_base_api
 * 主要功能：封装知识库前端访问后端 API 的请求函数。
 */

import {
  API_BASE_URL,
  DEFAULT_MANUAL_EDGE_WEIGHT,
  DEFAULT_QUERY_TOP_K,
} from '../constants/knowledge_base_constants';
import type {
  GraphPayload,
  KnowledgeBaseDocument,
  KnowledgeBaseJob,
  QueryResult,
} from '../types/knowledge_base';

/**
 * 发送 HTTP 请求并解析 JSON 响应。
 *
 * @param path - 接口路径。
 * @param init - fetch 初始化参数。
 * @returns 解析后的响应对象。
 * @throws 当请求失败时抛出错误。
 */
async function request_json<T>(path: string, init?: RequestInit): Promise<T> {
  const response: Response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const error_text: string = await response.text();
    throw new Error(error_text || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

/**
 * 获取文档列表。
 *
 * @returns 文档列表。
 */
export function fetch_documents(): Promise<KnowledgeBaseDocument[]> {
  return request_json<KnowledgeBaseDocument[]>('/api/documents');
}

/**
 * 获取图谱数据。
 *
 * @param document_id - 可选的文档过滤条件。
 * @param include_chunks - 是否返回切块节点。
 * @returns 图谱数据。
 */
export function fetch_graph(document_id?: string | null, include_chunks = true): Promise<GraphPayload> {
  const search_params: URLSearchParams = new URLSearchParams();
  if (document_id) {
    search_params.set('document_id', document_id);
  }
  search_params.set('include_chunks', String(include_chunks));
  return request_json<GraphPayload>(`/api/graph?${search_params.toString()}`);
}

/**
 * 获取单个任务状态。
 *
 * @param job_id - 任务主键。
 * @returns 任务详情。
 */
export function fetch_job(job_id: string): Promise<KnowledgeBaseJob> {
  return request_json<KnowledgeBaseJob>(`/api/jobs/${job_id}`);
}

/**
 * 上传文档并创建导入任务。
 *
 * @param file - 待上传文件。
 * @returns 任务与文档标识。
 */
export async function upload_document(file: File): Promise<{ job_id: string; document_id: string }> {
  const form_data: FormData = new FormData();
  form_data.append('file', file);
  return request_json<{ job_id: string; document_id: string }>('/api/files/import', {
    method: 'POST',
    body: form_data,
  });
}

/**
 * 创建手工图边。
 *
 * @param source_node_id - 源节点标识。
 * @param target_node_id - 目标节点标识。
 * @returns 创建后的边响应。
 */
export function create_manual_edge(source_node_id: string, target_node_id: string): Promise<{ edge: unknown }> {
  return request_json<{ edge: unknown }>('/api/edges', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_node_id,
      target_node_id,
      // 手工边默认高于普通边，便于在个性化 PageRank 中体现人工确认的连接强度。
      weight: DEFAULT_MANUAL_EDGE_WEIGHT,
      metadata: { created_from: 'frontend' },
    }),
  });
}

/**
 * 删除图边。
 *
 * @param edge_id - 边主键。
 * @returns 删除结果。
 */
export function delete_edge(edge_id: string): Promise<{ status: string }> {
  return request_json<{ status: string }>(`/api/edges/${edge_id}`, {
    method: 'DELETE',
  });
}

/**
 * 执行知识库问答查询。
 *
 * @param query - 用户问题。
 * @param document_ids - 可选的文档过滤范围。
 * @returns 查询结果。
 */
export function run_query(query: string, document_ids?: string[]): Promise<QueryResult> {
  return request_json<QueryResult>('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      document_ids: document_ids?.length ? document_ids : undefined,
      top_k: DEFAULT_QUERY_TOP_K,
    }),
  });
}
