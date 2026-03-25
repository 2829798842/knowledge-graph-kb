/**
 * Query-related API helpers.
 */

import type {
  AnswerQueryResult,
  EntitySearchItemRecord,
  RecordSearchItemRecord,
  RelationSearchItemRecord,
  SourceSearchItemRecord,
} from '../types/knowledge_base_types';
import { request_json } from './http_client';

interface EntitySearchResponse {
  items: EntitySearchItemRecord[];
}

interface RelationSearchResponse {
  items: RelationSearchItemRecord[];
}

interface RecordSearchResponse {
  items: RecordSearchItemRecord[];
}

interface SourceSearchResponse {
  items: SourceSearchItemRecord[];
}

export function answer_query(payload: {
  query: string;
  source_ids?: string[];
  worksheet_names?: string[];
  exact_first?: boolean;
  top_k?: number;
}): Promise<AnswerQueryResult> {
  return request_json<AnswerQueryResult>('/api/kb/search/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function search_records(payload: {
  query: string;
  source_ids?: string[];
  worksheet_names?: string[];
  filters?: Record<string, string>;
  limit?: number;
  mode?: 'exact_first' | 'hybrid';
}): Promise<RecordSearchItemRecord[]> {
  const response = await request_json<RecordSearchResponse>('/api/kb/search/records', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.items;
}

export async function search_entities(payload: {
  query: string;
  limit?: number;
}): Promise<EntitySearchItemRecord[]> {
  const response = await request_json<EntitySearchResponse>('/api/kb/search/entities', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.items;
}

export async function search_relations(payload: {
  query: string;
  limit?: number;
}): Promise<RelationSearchItemRecord[]> {
  const response = await request_json<RelationSearchResponse>('/api/kb/search/relations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.items;
}

export async function search_sources(payload: {
  query: string;
  limit?: number;
}): Promise<SourceSearchItemRecord[]> {
  const response = await request_json<SourceSearchResponse>('/api/kb/search/sources', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.items;
}
