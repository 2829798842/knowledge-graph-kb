/**
 * Query-related API helpers.
 */

import type {
  ChatSessionDetailRecord,
  ChatSessionRecord,
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

export function list_chat_sessions(limit: number = 50): Promise<ChatSessionRecord[]> {
  return request_json<ChatSessionRecord[]>(`/api/kb/chat/sessions?limit=${limit}`);
}

export function create_chat_session(payload: {
  title?: string;
  metadata?: Record<string, unknown>;
}): Promise<ChatSessionRecord> {
  return request_json<ChatSessionRecord>('/api/kb/chat/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function get_chat_session(session_id: string): Promise<ChatSessionDetailRecord> {
  return request_json<ChatSessionDetailRecord>(`/api/kb/chat/sessions/${session_id}`);
}

export function post_chat_message(
  session_id: string,
  payload: {
    content: string;
    source_ids?: string[];
    worksheet_names?: string[];
    top_k?: number;
  },
): Promise<ChatSessionDetailRecord> {
  return request_json<ChatSessionDetailRecord>(`/api/kb/chat/sessions/${session_id}/messages`, {
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
