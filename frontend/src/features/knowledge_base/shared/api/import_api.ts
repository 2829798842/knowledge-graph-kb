/**
 * Import-related API helpers.
 */

import type { ImportChunkRecord, ImportTaskRecord } from '../types/knowledge_base_types';
import { request_json } from './http_client';

interface UploadJobResponse {
  job: ImportTaskRecord;
}

export function list_import_jobs(): Promise<ImportTaskRecord[]> {
  return request_json<ImportTaskRecord[]>('/api/kb/imports/jobs');
}

export async function submit_upload_job(files: File[], strategy: string): Promise<UploadJobResponse> {
  const form_data = new FormData();
  files.forEach((file) => form_data.append('files', file));
  form_data.append('strategy', strategy);
  return request_json<UploadJobResponse>('/api/kb/imports/uploads', {
    method: 'POST',
    body: form_data,
  });
}

export function submit_paste_job(payload: {
  title: string;
  content: string;
  strategy: string;
  metadata?: Record<string, unknown>;
}): Promise<UploadJobResponse> {
  return request_json<UploadJobResponse>('/api/kb/imports/paste', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function submit_scan_job(payload: {
  root_path: string;
  glob_pattern: string;
  strategy: string;
}): Promise<UploadJobResponse> {
  return request_json<UploadJobResponse>('/api/kb/imports/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function submit_structured_job(
  route: 'openie' | 'convert',
  payload: {
    title: string;
    payload: Record<string, unknown>;
    strategy: string;
    metadata?: Record<string, unknown>;
  },
): Promise<UploadJobResponse> {
  return request_json<UploadJobResponse>(`/api/kb/imports/${route}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function get_import_job(job_id: string): Promise<ImportTaskRecord> {
  return request_json<ImportTaskRecord>(`/api/kb/imports/jobs/${job_id}`);
}

export function list_import_chunks(job_id: string, file_id: string): Promise<ImportChunkRecord[]> {
  return request_json<ImportChunkRecord[]>(`/api/kb/imports/jobs/${job_id}/files/${file_id}/chunks`);
}

export function cancel_import_job(job_id: string): Promise<ImportTaskRecord> {
  return request_json<ImportTaskRecord>(`/api/kb/imports/jobs/${job_id}/cancel`, { method: 'POST' });
}

export function retry_failed_job(job_id: string): Promise<UploadJobResponse> {
  return request_json<UploadJobResponse>(`/api/kb/imports/jobs/${job_id}/retry`, { method: 'POST' });
}
