/**
 * 知识库工作台的后端 API 调用辅助函数。
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
  ModelConfiguration,
  ModelConfigurationTestRequest,
  ModelConfigurationTestResult,
  ModelConfigurationUpdateRequest,
  QueryResult,
} from '../types/knowledge_base';

async function request_json<T>(path: string, init?: RequestInit): Promise<T> {
  const response: Response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const error_text: string = await response.text();
    let detail_message: string | null = null;
    try {
      const error_payload: { detail?: string } = JSON.parse(error_text) as { detail?: string };
      detail_message = typeof error_payload.detail === 'string' ? error_payload.detail.trim() : null;
    } catch {}
    if (detail_message) {
      throw new Error(detail_message);
    }
    throw new Error(error_text || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetch_documents(): Promise<KnowledgeBaseDocument[]> {
  return request_json<KnowledgeBaseDocument[]>('/api/documents');
}

export function fetch_graph(document_id?: string | null, include_chunks = true): Promise<GraphPayload> {
  const search_params: URLSearchParams = new URLSearchParams();
  if (document_id) {
    search_params.set('document_id', document_id);
  }
  search_params.set('include_chunks', String(include_chunks));
  return request_json<GraphPayload>(`/api/graph?${search_params.toString()}`);
}

export function fetch_job(job_id: string): Promise<KnowledgeBaseJob> {
  return request_json<KnowledgeBaseJob>(`/api/jobs/${job_id}`);
}

export function fetch_model_configuration(): Promise<ModelConfiguration> {
  return request_json<ModelConfiguration>('/api/model-config');
}

export function test_model_configuration(
  payload: ModelConfigurationTestRequest,
): Promise<ModelConfigurationTestResult> {
  return request_json<ModelConfigurationTestResult>('/api/model-config/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function update_model_configuration(
  payload: ModelConfigurationUpdateRequest,
): Promise<ModelConfiguration> {
  return request_json<ModelConfiguration>('/api/model-config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function upload_document(file: File): Promise<{ job_id: string; document_id: string }> {
  const form_data: FormData = new FormData();
  form_data.append('file', file);
  return request_json<{ job_id: string; document_id: string }>('/api/files/import', {
    method: 'POST',
    body: form_data,
  });
}

export function create_manual_edge(source_node_id: string, target_node_id: string): Promise<{ edge: unknown }> {
  return request_json<{ edge: unknown }>('/api/edges', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_node_id,
      target_node_id,
      weight: DEFAULT_MANUAL_EDGE_WEIGHT,
      metadata: { created_from: 'frontend' },
    }),
  });
}

export function delete_edge(edge_id: string): Promise<{ status: string }> {
  return request_json<{ status: string }>(`/api/edges/${edge_id}`, {
    method: 'DELETE',
  });
}

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
