import { describe, expect, it } from 'vitest';

import type { ImportTaskRecord } from '../../shared/types/knowledge_base_types';
import { format_import_task_short_id, sort_import_tasks } from './import_task_order';

function build_task(overrides: Partial<ImportTaskRecord>): ImportTaskRecord {
  return {
    id: '00000000-0000-0000-0000-000000000000',
    source: 'upload',
    input_mode: 'file',
    strategy: 'auto',
    status: 'completed',
    current_step: 'completed',
    progress: 100,
    total_files: 1,
    completed_files: 1,
    failed_files: 0,
    total_chunks: 0,
    completed_chunks: 0,
    failed_chunks: 0,
    message: null,
    error: null,
    params: {},
    failure_stage: null,
    step_durations: {},
    retry_of: null,
    stats: {},
    created_at: '2026-03-25T00:00:00.000Z',
    started_at: null,
    finished_at: null,
    updated_at: '2026-03-25T00:00:00.000Z',
    files: [],
    ...overrides,
  };
}

describe('sort_import_tasks', () => {
  it('keeps active tasks at the top but orders finished tasks by newest first', () => {
    const ordered = sort_import_tasks([
      build_task({
        id: 'old-failed-0000-0000-000000000000',
        status: 'failed',
        current_step: 'failed',
        error: 'UNIQUE constraint failed: paragraphs.source_id, paragraphs.position',
        created_at: '2026-03-25T11:25:32.767Z',
      }),
      build_task({
        id: 'latest-completed-0000-000000000000',
        status: 'completed',
        current_step: 'completed',
        created_at: '2026-03-26T00:35:27.347Z',
      }),
      build_task({
        id: 'active-running-0000-000000000000',
        status: 'running',
        current_step: 'embedding',
        progress: 42,
        completed_files: 0,
        created_at: '2026-03-26T00:10:00.000Z',
      }),
    ]);

    expect(ordered.map((task) => task.id)).toEqual([
      'active-running-0000-000000000000',
      'latest-completed-0000-000000000000',
      'old-failed-0000-0000-000000000000',
    ]);
  });

  it('keeps running tasks ahead of queued tasks inside the active bucket', () => {
    const ordered = sort_import_tasks([
      build_task({
        id: 'queued-task-0000-000000000000000',
        status: 'queued',
        current_step: 'queued',
        created_at: '2026-03-26T00:35:27.347Z',
      }),
      build_task({
        id: 'running-task-0000-0000000000000',
        status: 'running',
        current_step: 'embedding',
        progress: 36,
        created_at: '2026-03-26T00:34:00.000Z',
      }),
    ]);

    expect(ordered.map((task) => task.id)).toEqual([
      'running-task-0000-0000000000000',
      'queued-task-0000-000000000000000',
    ]);
  });
});

describe('format_import_task_short_id', () => {
  it('returns the first eight characters of the job id', () => {
    expect(format_import_task_short_id('582bd83e-dfa8-4a0d-aff8-274a1775083b')).toBe('582bd83e');
  });
});
