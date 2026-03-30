/**
 * Source-related API helpers.
 */

import type { ParagraphRecord, SourceDetailRecord, SourceRecord } from '../types/knowledge_base_types';
import { build_query_string, request_json } from './http_client';

interface SourceParagraphsResponse {
  items: ParagraphRecord[];
}

export function list_sources(keyword?: string): Promise<SourceRecord[]> {
  return request_json<SourceRecord[]>(`/api/kb/sources${build_query_string({ keyword, limit: 100 })}`);
}

export function get_source_detail(source_id: string): Promise<SourceDetailRecord> {
  return request_json<SourceDetailRecord>(`/api/kb/sources/${source_id}`);
}

export function update_source(
  source_id: string,
  payload: {
    name?: string;
    summary?: string;
    metadata?: Record<string, unknown>;
  },
): Promise<SourceRecord> {
  return request_json<SourceRecord>(`/api/kb/sources/${source_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function delete_source(source_id: string): Promise<{ status: string }> {
  return request_json<{ status: string }>(`/api/kb/sources/${source_id}`, {
    method: 'DELETE',
  });
}

export async function list_source_paragraphs(source_id: string): Promise<ParagraphRecord[]> {
  const response = await request_json<SourceParagraphsResponse>(`/api/kb/sources/${source_id}/paragraphs`);
  return response.items;
}
