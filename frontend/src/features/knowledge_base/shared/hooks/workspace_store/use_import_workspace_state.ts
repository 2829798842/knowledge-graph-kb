/**
 * Import-job state and import actions.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type Dispatch, type SetStateAction } from 'react';

import {
  cancel_import_job,
  list_import_jobs,
  retry_failed_job,
  submit_paste_job,
  submit_scan_job,
  submit_structured_job,
  submit_upload_job,
} from '../../api/import_api';
import { kb_query_keys } from '../../api/query_client';
import type { ImportTaskRecord } from '../../types/knowledge_base_types';

const ACTIVE_JOB_STATUSES: Set<string> = new Set(['queued', 'running']);

interface ImportWorkspaceStateProps {
  refresh_sources: () => Promise<void>;
  set_message: Dispatch<SetStateAction<string>>;
  set_error: Dispatch<SetStateAction<string | null>>;
}

export function use_import_workspace_state(props: ImportWorkspaceStateProps) {
  const { refresh_sources, set_message, set_error } = props;
  const query_client = useQueryClient();

  const jobs_query = useQuery({
    queryKey: kb_query_keys.import_jobs(),
    queryFn: list_import_jobs,
    refetchInterval: (query) => {
      const jobs = (query.state.data as ImportTaskRecord[] | undefined) ?? [];
      return jobs.some((job) => ACTIVE_JOB_STATUSES.has(job.status)) ? 1200 : false;
    },
  });

  async function refresh_jobs(): Promise<void> {
    try {
      await query_client.invalidateQueries({ queryKey: kb_query_keys.import_jobs() });
      await query_client.refetchQueries({ queryKey: kb_query_keys.import_jobs() });
    } catch (refresh_error) {
      set_error((refresh_error as Error).message);
    }
  }

  async function refresh_related_queries(): Promise<void> {
    await Promise.all([
      refresh_jobs(),
      refresh_sources(),
      query_client.invalidateQueries({ queryKey: ['kb', 'graph'] }),
      query_client.invalidateQueries({ queryKey: kb_query_keys.manual_relations() }),
    ]);
  }

  const upload_mutation = useMutation({
    mutationFn: ({ files, strategy }: { files: File[]; strategy: string }) => submit_upload_job(files, strategy),
    onSuccess: async (response) => {
      set_message(`已提交上传任务：${response.job.id}`);
      set_error(null);
      await refresh_related_queries();
    },
    onError: (submit_error) => {
      set_error((submit_error as Error).message);
    },
  });

  const paste_mutation = useMutation({
    mutationFn: (payload: { title: string; content: string; strategy: string; metadata?: Record<string, unknown> }) =>
      submit_paste_job(payload),
    onSuccess: async (response) => {
      set_message(`已提交粘贴任务：${response.job.id}`);
      set_error(null);
      await refresh_related_queries();
    },
    onError: (submit_error) => {
      set_error((submit_error as Error).message);
    },
  });

  const scan_mutation = useMutation({
    mutationFn: (payload: { root_path: string; glob_pattern: string; strategy: string }) => submit_scan_job(payload),
    onSuccess: async (response) => {
      set_message(`已提交扫描任务：${response.job.id}`);
      set_error(null);
      await refresh_related_queries();
    },
    onError: (submit_error) => {
      set_error((submit_error as Error).message);
    },
  });

  const structured_mutation = useMutation({
    mutationFn: (payload: {
      route: 'openie' | 'convert';
      title: string;
      payload: Record<string, unknown>;
      strategy: string;
    }) => submit_structured_job(payload.route, payload),
    onSuccess: async (response) => {
      set_message(`已提交结构化任务：${response.job.id}`);
      set_error(null);
      await refresh_related_queries();
    },
    onError: (submit_error) => {
      set_error((submit_error as Error).message);
    },
  });

  const cancel_mutation = useMutation({
    mutationFn: (job_id: string) => cancel_import_job(job_id),
    onSuccess: async (job) => {
      set_message(`已请求取消任务：${job.id}`);
      set_error(null);
      await refresh_jobs();
    },
    onError: (cancel_error) => {
      set_error((cancel_error as Error).message);
    },
  });

  const retry_mutation = useMutation({
    mutationFn: (job_id: string) => retry_failed_job(job_id),
    onSuccess: async (response) => {
      set_message(`已创建重试任务：${response.job.id}`);
      set_error(null);
      await refresh_related_queries();
    },
    onError: (retry_error) => {
      set_error((retry_error as Error).message);
    },
  });

  async function upload_files(files: File[], strategy: string): Promise<void> {
    if (!files.length) {
      return;
    }
    await upload_mutation.mutateAsync({ files, strategy });
  }

  async function import_paste_text(title: string, content: string, strategy: string): Promise<void> {
    await paste_mutation.mutateAsync({ title, content, strategy });
  }

  async function import_scan_path(root_path: string, glob_pattern: string, strategy: string): Promise<void> {
    await scan_mutation.mutateAsync({ root_path, glob_pattern, strategy });
  }

  async function import_structured_payload(
    mode: 'openie' | 'convert',
    title: string,
    payload_text: string,
    strategy: string,
  ): Promise<void> {
    const payload: Record<string, unknown> = JSON.parse(payload_text);
    await structured_mutation.mutateAsync({ route: mode, title, payload, strategy });
  }

  async function cancel_task(task_id: string): Promise<void> {
    await cancel_mutation.mutateAsync(task_id);
  }

  async function retry_task(task_id: string): Promise<void> {
    await retry_mutation.mutateAsync(task_id);
  }

  return {
    tasks: jobs_query.data ?? [],
    refresh_tasks: refresh_jobs,
    is_submitting_import:
      upload_mutation.isPending ||
      paste_mutation.isPending ||
      scan_mutation.isPending ||
      structured_mutation.isPending,
    upload_files,
    import_paste_text,
    import_scan_path,
    import_structured_payload,
    cancel_task,
    retry_task,
  };
}
