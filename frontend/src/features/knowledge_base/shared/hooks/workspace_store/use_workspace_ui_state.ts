import { useEffect, useState } from 'react';

import type { GraphDrawerMode, GraphViewportMode, QueryMode, WorkspaceTab } from '../../types/knowledge_base_types';

const STORAGE_KEYS = {
  sidebar_collapsed: 'kb.v6.sidebar_collapsed',
  sidebar_width: 'kb.v6.sidebar_width',
  graph_viewport_mode: 'kb.v6.graph_viewport_mode',
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

function read_viewport_mode(): GraphViewportMode {
  if (typeof window === 'undefined') {
    return 'fit-all';
  }
  const value = window.localStorage.getItem(STORAGE_KEYS.graph_viewport_mode);
  return value === 'focus-selection' ? 'focus-selection' : 'fit-all';
}

export function use_workspace_ui_state() {
  const [active_workspace, set_active_workspace] = useState<WorkspaceTab>('chat');
  const [query_mode, set_query_mode] = useState<QueryMode>('answer');
  const [last_query_text, set_last_query_text] = useState<string>('');
  const [message, set_message] = useState<string>('知识库已就绪。');
  const [error, set_error] = useState<string | null>(null);
  const [is_settings_open, set_is_settings_open] = useState<boolean>(false);
  const [is_source_library_open, set_is_source_library_open] = useState<boolean>(false);
  const [sidebar_collapsed, set_sidebar_collapsed] = useState<boolean>(() =>
    read_boolean(STORAGE_KEYS.sidebar_collapsed, false),
  );
  const [sidebar_width, set_sidebar_width] = useState<number>(() => read_number(STORAGE_KEYS.sidebar_width, DEFAULT_SIDEBAR_WIDTH));
  const [graph_controls_open, set_graph_controls_open] = useState<boolean>(false);
  const [graph_inspector_open, set_graph_inspector_open] = useState<boolean>(false);
  const [graph_viewport_mode, set_graph_viewport_mode] = useState<GraphViewportMode>(() => read_viewport_mode());
  const [active_graph_drawer, set_active_graph_drawer] = useState<GraphDrawerMode>(null);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEYS.sidebar_collapsed, String(sidebar_collapsed));
  }, [sidebar_collapsed]);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEYS.sidebar_width, String(sidebar_width));
  }, [sidebar_width]);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEYS.graph_viewport_mode, graph_viewport_mode);
  }, [graph_viewport_mode]);

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
    graph_controls_open,
    set_graph_controls_open,
    graph_inspector_open,
    set_graph_inspector_open,
    graph_viewport_mode,
    set_graph_viewport_mode,
    active_graph_drawer,
    set_active_graph_drawer,
  };
}
