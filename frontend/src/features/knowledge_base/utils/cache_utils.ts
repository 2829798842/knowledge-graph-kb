/**
 * 模块名称：features/knowledge_base/utils/cache_utils
 * 主要功能：提供文档列表、图谱结果和工作区偏好的本地缓存能力。
 */

import { EMPTY_GRAPH } from '../constants/knowledge_base_constants';
import type { GraphPayload, KnowledgeBaseDocument } from '../types/knowledge_base';

const CACHE_PREFIX: string = 'knowledge_graph_kb';
const DOCUMENTS_CACHE_KEY: string = `${CACHE_PREFIX}:documents`;
const WORKSPACE_PREFERENCES_KEY: string = `${CACHE_PREFIX}:workspace_preferences`;

/**
 * 工作区偏好配置。
 */
export interface WorkspacePreferences {
  selected_document_id: string | null;
  include_chunks: boolean;
}

/**
 * 判断当前是否运行在浏览器环境。
 *
 * @returns 是否可用浏览器存储。
 */
function is_browser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

/**
 * 读取 JSON 缓存。
 *
 * @param key - 缓存键。
 * @returns 解析后的缓存对象。
 */
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

/**
 * 写入 JSON 缓存。
 *
 * @param key - 缓存键。
 * @param value - 待写入的缓存值。
 */
function write_json<T>(key: string, value: T): void {
  if (!is_browser()) {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
}

/**
 * 构建图谱缓存键。
 *
 * @param document_id - 当前筛选文档。
 * @param include_chunks - 是否包含切块节点。
 * @returns 图谱缓存键。
 */
function build_graph_cache_key(document_id: string | null, include_chunks: boolean): string {
  const document_segment: string = document_id ?? 'all';
  const chunk_segment: string = include_chunks ? 'with_chunks' : 'without_chunks';
  return `${CACHE_PREFIX}:graph:${document_segment}:${chunk_segment}`;
}

/**
 * 读取文档列表缓存。
 *
 * @returns 文档列表缓存。
 */
export function read_documents_cache(): KnowledgeBaseDocument[] {
  return read_json<KnowledgeBaseDocument[]>(DOCUMENTS_CACHE_KEY) ?? [];
}

/**
 * 写入文档列表缓存。
 *
 * @param documents - 最新文档列表。
 */
export function write_documents_cache(documents: KnowledgeBaseDocument[]): void {
  write_json(DOCUMENTS_CACHE_KEY, documents);
}

/**
 * 读取图谱缓存。
 *
 * @param document_id - 当前筛选文档。
 * @param include_chunks - 是否包含切块节点。
 * @returns 图谱缓存。
 */
export function read_graph_cache(document_id: string | null, include_chunks: boolean): GraphPayload {
  return read_json<GraphPayload>(build_graph_cache_key(document_id, include_chunks)) ?? EMPTY_GRAPH;
}

/**
 * 写入图谱缓存。
 *
 * @param document_id - 当前筛选文档。
 * @param include_chunks - 是否包含切块节点。
 * @param graph - 最新图谱结果。
 */
export function write_graph_cache(
  document_id: string | null,
  include_chunks: boolean,
  graph: GraphPayload,
): void {
  write_json(build_graph_cache_key(document_id, include_chunks), graph);
}

/**
 * 读取工作区偏好。
 *
 * @returns 当前工作区偏好。
 */
export function read_workspace_preferences(): WorkspacePreferences {
  return (
    read_json<WorkspacePreferences>(WORKSPACE_PREFERENCES_KEY) ?? {
      selected_document_id: null,
      include_chunks: true,
    }
  );
}

/**
 * 写入工作区偏好。
 *
 * @param preferences - 最新工作区偏好。
 */
export function write_workspace_preferences(preferences: WorkspacePreferences): void {
  write_json(WORKSPACE_PREFERENCES_KEY, preferences);
}
