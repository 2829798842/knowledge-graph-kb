/**
 * Workspace-level UI state.
 */

import { useState } from 'react';

import type { QueryMode, WorkspaceTab } from '../../types/knowledge_base_types';

export function use_workspace_ui_state() {
  const [active_workspace, set_active_workspace] = useState<WorkspaceTab>('import');
  const [query_mode, set_query_mode] = useState<QueryMode>('answer');
  const [last_query_text, set_last_query_text] = useState<string>('');
  const [message, set_message] = useState<string>('知识库工作台已就绪。');
  const [error, set_error] = useState<string | null>(null);

  return {
    active_workspace,
    set_active_workspace,
    query_mode,
    set_query_mode,
    last_query_text,
    set_last_query_text,
    message,
    set_message,
    error,
    set_error,
  };
}
