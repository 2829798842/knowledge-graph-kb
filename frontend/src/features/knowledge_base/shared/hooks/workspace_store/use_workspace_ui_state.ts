import { useEffect, useState } from 'react';

import type { QueryMode, WorkspaceTab } from '../../types/knowledge_base_types';

const STORAGE_KEYS = {
  sidebar_collapsed: 'kb.v7.sidebar_collapsed',
  sidebar_width: 'kb.v7.sidebar_width',
} as const;

const DEFAULT_SIDEBAR_WIDTH = 236;

function read_boolean(key: string, fallback: boolean): boolean {
  if (typeof window === 'undefined') {
    return fallback;
  }

  const value = window.localStorage.getItem(key);
  if (value === null) {
    return fallback;
  }

  return value === 'true';
}

function read_number(key: string, fallback: number): number {
  if (typeof window === 'undefined') {
    return fallback;
  }

  const value = Number(window.localStorage.getItem(key));
  return Number.isFinite(value) ? value : fallback;
}

export function use_workspace_ui_state() {
  const [active_workspace, set_active_workspace] = useState<WorkspaceTab>('chat');
  const [query_mode, set_query_mode] = useState<QueryMode>('answer');
  const [last_query_text, set_last_query_text] = useState('');
  const [message, set_message] = useState('知识库已就绪。');
  const [error, set_error] = useState<string | null>(null);
  const [is_settings_open, set_is_settings_open] = useState(false);
  const [is_source_library_open, set_is_source_library_open] = useState(false);
  const [sidebar_collapsed, set_sidebar_collapsed] = useState<boolean>(() =>
    read_boolean(STORAGE_KEYS.sidebar_collapsed, false),
  );
  const [sidebar_width, set_sidebar_width] = useState<number>(() =>
    read_number(STORAGE_KEYS.sidebar_width, DEFAULT_SIDEBAR_WIDTH),
  );

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEYS.sidebar_collapsed, String(sidebar_collapsed));
  }, [sidebar_collapsed]);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEYS.sidebar_width, String(sidebar_width));
  }, [sidebar_width]);

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
    is_settings_open,
    set_is_settings_open,
    is_source_library_open,
    set_is_source_library_open,
    sidebar_collapsed,
    set_sidebar_collapsed,
    sidebar_width,
    set_sidebar_width,
  };
}
