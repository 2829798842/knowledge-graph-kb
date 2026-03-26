import { TASK_STATUS_ORDER } from '../../shared/config/ui_constants';
import type { ImportTaskRecord } from '../../shared/types/knowledge_base_types';

const ACTIVE_TASK_STATUSES: ReadonlySet<string> = new Set(['queued', 'running']);

function parse_task_timestamp(value: string): number {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

export function is_import_task_active(task: ImportTaskRecord): boolean {
  return ACTIVE_TASK_STATUSES.has(task.status);
}

export function sort_import_tasks(tasks: ImportTaskRecord[]): ImportTaskRecord[] {
  return [...tasks].sort((left_task, right_task) => {
    const left_is_active = is_import_task_active(left_task);
    const right_is_active = is_import_task_active(right_task);
    if (left_is_active !== right_is_active) {
      return left_is_active ? -1 : 1;
    }

    if (left_is_active && right_is_active) {
      const status_diff = (TASK_STATUS_ORDER[left_task.status] ?? 99) - (TASK_STATUS_ORDER[right_task.status] ?? 99);
      if (status_diff !== 0) {
        return status_diff;
      }
    }

    const created_at_diff = parse_task_timestamp(right_task.created_at) - parse_task_timestamp(left_task.created_at);
    if (created_at_diff !== 0) {
      return created_at_diff;
    }

    const status_diff = (TASK_STATUS_ORDER[left_task.status] ?? 99) - (TASK_STATUS_ORDER[right_task.status] ?? 99);
    if (status_diff !== 0) {
      return status_diff;
    }

    return right_task.id.localeCompare(left_task.id);
  });
}

export function format_import_task_timestamp(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(timestamp);
}

export function format_import_task_short_id(task_id: string): string {
  return task_id.slice(0, 8);
}
