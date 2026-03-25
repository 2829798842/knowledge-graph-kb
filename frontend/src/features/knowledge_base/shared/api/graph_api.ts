/**
 * Graph-related API helpers.
 */

import type {
  GraphEdgeDetailRecord,
  GraphNodeDetailRecord,
  KnowledgeGraphRecord,
  ManualRelationRecord,
} from '../types/knowledge_base_types';
import { build_query_string, request_json } from './http_client';

interface GraphQueryOptions {
  source_ids?: string[];
  include_paragraphs?: boolean;
  density?: number;
}

export function fetch_graph(options: GraphQueryOptions): Promise<KnowledgeGraphRecord> {
  return request_json<KnowledgeGraphRecord>(
    `/api/kb/graph${build_query_string({
      source_ids: options.source_ids,
      include_paragraphs: options.include_paragraphs ?? true,
      density: options.density ?? 100,
    })}`,
  );
}

export function get_graph_node_detail(node_id: string): Promise<GraphNodeDetailRecord> {
  return request_json<GraphNodeDetailRecord>(`/api/kb/graph/nodes/${encodeURIComponent(node_id)}`);
}

export function get_graph_edge_detail(edge_id: string): Promise<GraphEdgeDetailRecord> {
  return request_json<GraphEdgeDetailRecord>(`/api/kb/graph/edges/${encodeURIComponent(edge_id)}`);
}

export function list_manual_relations(): Promise<ManualRelationRecord[]> {
  return request_json<ManualRelationRecord[]>('/api/kb/graph/manual-relations');
}

export function create_manual_relation(payload: {
  subject_node_id: string;
  predicate: string;
  object_node_id: string;
  weight: number;
  metadata?: Record<string, unknown>;
}): Promise<ManualRelationRecord> {
  return request_json<ManualRelationRecord>('/api/kb/graph/manual-relations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function delete_manual_relation(relation_id: string): Promise<{ status: string }> {
  return request_json<{ status: string }>(`/api/kb/graph/manual-relations/${relation_id}`, {
    method: 'DELETE',
  });
}
