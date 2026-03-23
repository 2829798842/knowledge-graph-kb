/**
 * 模块名称：features/knowledge_base/constants/knowledge_base_constants
 * 主要功能：集中管理知识库功能使用的常量。
 */

import type { GraphPayload } from '../types/knowledge_base';

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');
export const DEFAULT_MANUAL_EDGE_WEIGHT: number = 1.25;
export const DEFAULT_QUERY_TOP_K: number = 6;
export const JOB_POLL_INTERVAL_MS: number = 2000;
export const INITIAL_STATUS_MESSAGE: string = '准备就绪，可以导入你的第一份文档。';
export const EMPTY_GRAPH: GraphPayload = { nodes: [], edges: [] };
