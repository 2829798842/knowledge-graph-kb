/**
 * 知识库工作台的本地缓存辅助函数。
 */

import { EMPTY_GRAPH } from '../constants/knowledge_base_constants';
import type { GraphPayload, KnowledgeBaseDocument, ModelConfiguration } from '../types/knowledge_base';

const CACHE_PREFIX: string = 'knowledge_graph_kb';
const DOCUMENTS_CACHE_KEY: string = `${CACHE_PREFIX}:documents`;
const MODEL_CONFIGURATION_CACHE_KEY: string = `${CACHE_PREFIX}:model_configuration`;
const WORKSPACE_PREFERENCES_KEY: string = `${CACHE_PREFIX}:workspace_preferences`;

export interface WorkspacePreferences {
  selected_document_id: string | null;
  include_chunks: boolean;
}

function is_browser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function read_json<T>(key: string): T | null {
  if (!is_browser()) {
    return null;
  }

  const raw_value: string | null = window.localStorage.getItem(key);
  if (!raw_value) {
    return null;
  }

  try {
    return JSON.parse(raw_value) as T;
  } catch {
    window.localStorage.removeItem(key);
    return null;
  }
}

function write_json<T>(key: string, value: T): void {
  if (!is_browser()) {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
}

function build_graph_cache_key(document_id: string | null, include_chunks: boolean): string {
  const document_segment: string = document_id ?? 'all';
  const chunk_segment: string = include_chunks ? 'with_chunks' : 'without_chunks';
  return `${CACHE_PREFIX}:graph:${document_segment}:${chunk_segment}`;
}

export function read_documents_cache(): KnowledgeBaseDocument[] {
  return read_json<KnowledgeBaseDocument[]>(DOCUMENTS_CACHE_KEY) ?? [];
}

export function write_documents_cache(documents: KnowledgeBaseDocument[]): void {
  write_json(DOCUMENTS_CACHE_KEY, documents);
}

export function read_graph_cache(document_id: string | null, include_chunks: boolean): GraphPayload {
  return read_json<GraphPayload>(build_graph_cache_key(document_id, include_chunks)) ?? EMPTY_GRAPH;
}

export function write_graph_cache(
  document_id: string | null,
  include_chunks: boolean,
  graph: GraphPayload,
): void {
  write_json(build_graph_cache_key(document_id, include_chunks), graph);
}

export function read_model_configuration_cache(): ModelConfiguration | null {
  return read_json<ModelConfiguration>(MODEL_CONFIGURATION_CACHE_KEY);
}

export function write_model_configuration_cache(model_configuration: ModelConfiguration): void {
  write_json(MODEL_CONFIGURATION_CACHE_KEY, model_configuration);
}

export function read_workspace_preferences(): WorkspacePreferences {
  return (
    read_json<WorkspacePreferences>(WORKSPACE_PREFERENCES_KEY) ?? {
      selected_document_id: null,
      include_chunks: true,
    }
  );
}

export function write_workspace_preferences(preferences: WorkspacePreferences): void {
  write_json(WORKSPACE_PREFERENCES_KEY, preferences);
}
