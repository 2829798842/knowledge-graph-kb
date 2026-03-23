/**
 * 模块名称：features/knowledge_base/utils/job_utils
 * 主要功能：提供任务轮询、合并与占位任务创建的辅助函数。
 */

import type { KnowledgeBaseJob } from '../types/knowledge_base';

/**
 * 创建新上传文件对应的待处理任务。
 *
 * @param job_id - 任务标识。
 * @param document_id - 文档标识。
 * @returns 前端本地任务占位对象。
 */
export function create_pending_job(job_id: string, document_id: string): KnowledgeBaseJob {
  const created_at: string = new Date().toISOString();
  return {
    id: job_id,
    document_id,
    status: 'pending',
    error_message: null,
    created_at,
    updated_at: created_at,
  };
}

/**
 * 获取当前仍需轮询的任务标识列表。
 *
 * @param jobs - 当前任务列表。
 * @returns 活跃任务标识列表。
 */
export function get_active_job_ids(jobs: KnowledgeBaseJob[]): string[] {
  return jobs
    .filter((job) => job.status === 'pending' || job.status === 'processing')
    .map((job) => job.id);
}

/**
 * 合并任务列表并按创建时间倒序返回。
 *
 * @param current_jobs - 现有任务列表。
 * @param next_jobs - 新任务列表。
 * @returns 合并后的任务列表。
 */
export function merge_jobs(
  current_jobs: KnowledgeBaseJob[],
  next_jobs: KnowledgeBaseJob[],
): KnowledgeBaseJob[] {
  const job_map: Map<string, KnowledgeBaseJob> = new Map<string, KnowledgeBaseJob>();
  [...current_jobs, ...next_jobs].forEach((job) => job_map.set(job.id, job));
  return [...job_map.values()].sort((left, right) => right.created_at.localeCompare(left.created_at));
}
