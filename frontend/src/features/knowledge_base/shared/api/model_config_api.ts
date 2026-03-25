/**
 * Model-configuration API helpers.
 */

import { request_json } from './http_client';
import type { ModelConfigurationRecord, ModelConfigurationTestRecord } from '../types/knowledge_base_types';

interface ModelConfigurationUpdatePayload {
  provider: string;
  base_url: string;
  llm_model: string;
  embedding_model: string;
  api_key: string | null;
  clear_api_key: boolean;
}

interface ModelConfigurationTestPayload {
  provider: string;
  base_url: string;
  llm_model: string;
  embedding_model: string;
  api_key: string | null;
  use_saved_api_key: boolean;
}

export async function fetch_model_configuration(): Promise<ModelConfigurationRecord> {
  return request_json<ModelConfigurationRecord>('/api/kb/config/model');
}

export async function update_model_configuration(
  payload: ModelConfigurationUpdatePayload,
): Promise<ModelConfigurationRecord> {
  return request_json<ModelConfigurationRecord>('/api/kb/config/model', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function test_model_configuration(
  payload: ModelConfigurationTestPayload,
): Promise<ModelConfigurationTestRecord> {
  return request_json<ModelConfigurationTestRecord>('/api/kb/config/model/test', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

