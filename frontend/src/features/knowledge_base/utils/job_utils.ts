/**
 * 模块名称：features/knowledge_base/utils/job_utils
 * 主要功能：提供任务轮询、合并与按文档检索最新任务的辅助函数。
 */

import type { KnowledgeBaseJob } from '../types/knowledge_base';

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

/**
 * 获取某个文档最近一次任务。
 *
 * @param jobs - 当前任务列表。
 * @param document_id - 文档标识。
 * @returns 最近一次任务；若不存在则返回 `null`。
 */
export function get_latest_job_for_document(
  jobs: KnowledgeBaseJob[],
  document_id: string,
): KnowledgeBaseJob | null {
  const matched_jobs: KnowledgeBaseJob[] = jobs.filter((job) => job.document_id === document_id);
  if (!matched_jobs.length) {
    return null;
  }
  matched_jobs.sort((left, right) => right.created_at.localeCompare(left.created_at));
  return matched_jobs[0];
}

/**
 * 格式化任务当前阶段的细粒度进度文案。
 *
 * @param job - 当前任务。
 * @returns 细粒度阶段进度文案；若当前阶段没有子进度则返回 `null`。
 */
export function format_job_stage_detail(job: KnowledgeBaseJob): string | null {
  const stage_total: number = typeof job.stage_total === 'number' ? job.stage_total : 0;
  const stage_current: number = typeof job.stage_current === 'number' ? job.stage_current : 0;
  const stage_unit: string | null = typeof job.stage_unit === 'string' ? job.stage_unit : null;

  if (!stage_total || !stage_unit) {
    return null;
  }

  if (stage_current <= 0) {
    return `共 ${stage_total} 个${stage_unit}`;
  }

  const safe_current: number = Math.min(stage_current, stage_total);
  return `第 ${safe_current}/${stage_total} 个${stage_unit}`;
}
