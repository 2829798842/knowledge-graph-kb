/**
 * 模块名称：features/knowledge_base/constants/knowledge_base_constants
 * 主要功能：定义知识库工作台共享常量。
 */

import type { GraphPayload, ModelProvider } from '../types/knowledge_base';

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');
export const DEFAULT_MANUAL_EDGE_WEIGHT: number = 1.25;
export const DEFAULT_QUERY_TOP_K: number = 6;
export const JOB_POLL_INTERVAL_MS: number = 2000;
export const INITIAL_STATUS_MESSAGE: string = '准备就绪，可以先上传文档，再手动开始抽取。';
export const EMPTY_GRAPH: GraphPayload = { nodes: [], edges: [] };
export const MODEL_PROVIDER_OPTIONS: Array<{ value: ModelProvider; label: string }> = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'siliconflow', label: 'SiliconFlow' },
  { value: 'custom', label: '自定义兼容供应商' },
];
export const MODEL_PROVIDER_BASE_URLS: Record<ModelProvider, string> = {
  openai: 'https://api.openai.com/v1',
  openrouter: 'https://openrouter.ai/api/v1',
  siliconflow: 'https://api.siliconflow.cn/v1',
  custom: '',
};
