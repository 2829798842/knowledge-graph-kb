import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';

import { kb_query_keys } from '../../api/query_client';
import {
  delete_source,
  get_source_detail,
  list_source_paragraphs,
  list_sources,
  update_source,
} from '../../api/source_api';
import type {
  ParagraphRecord,
  SourceDetailRecord,
  SourceRecord,
  WorkspaceTab,
} from '../../types/knowledge_base_types';

interface SourceWorkspaceStateProps {
  active_workspace: WorkspaceTab;
  is_source_library_open: boolean;
  set_message: Dispatch<SetStateAction<string>>;
  set_error: Dispatch<SetStateAction<string | null>>;
}

export function use_source_workspace_state(props: SourceWorkspaceStateProps) {
  const { active_workspace, is_source_library_open, set_message, set_error } = props;
  const query_client = useQueryClient();
  const [selected_source_browser_id, set_selected_source_browser_id] = useState<string | null>(null);

  const sources_query = useQuery({
    queryKey: kb_query_keys.source_list(),
    queryFn: () => list_sources(),
  });

  const source_detail_query = useQuery({
    queryKey: kb_query_keys.source_detail(selected_source_browser_id),
    queryFn: () => get_source_detail(selected_source_browser_id!),
    enabled: Boolean(selected_source_browser_id),
  });

  const source_paragraphs_query = useQuery({
    queryKey: kb_query_keys.source_paragraphs(selected_source_browser_id),
    queryFn: () => list_source_paragraphs(selected_source_browser_id!),
    enabled: Boolean(selected_source_browser_id),
  });

  async function refresh_sources(_keyword?: string): Promise<void> {
    try {
      await query_client.invalidateQueries({ queryKey: kb_query_keys.source_list() });
      await query_client.refetchQueries({ queryKey: kb_query_keys.source_list() });
    } catch (refresh_error) {
      set_error((refresh_error as Error).message);
    }
  }

  const update_source_mutation = useMutation({
    mutationFn: (payload: { source_id: string; name?: string; summary?: string; metadata?: Record<string, unknown> }) =>
      update_source(payload.source_id, {
        name: payload.name,
        summary: payload.summary,
        metadata: payload.metadata,
      }),
    onSuccess: async (source) => {
      set_message(`来源已更新：${source.name}`);
      set_error(null);
      await Promise.all([
        query_client.invalidateQueries({ queryKey: kb_query_keys.source_list() }),
        query_client.invalidateQueries({ queryKey: kb_query_keys.source_detail(source.id) }),
        query_client.invalidateQueries({ queryKey: ['kb', 'graph'] }),
      ]);
    },
    onError: (source_error) => {
      set_error((source_error as Error).message);
    },
  });

  const delete_source_mutation = useMutation({
    mutationFn: (source_id: string) => delete_source(source_id),
    onSuccess: async (_result, source_id) => {
      set_selected_source_browser_id((current) => (current === source_id ? null : current));
      set_message('来源已删除。');
      set_error(null);
      await Promise.all([
        query_client.invalidateQueries({ queryKey: kb_query_keys.source_list() }),
        query_client.invalidateQueries({ queryKey: ['kb', 'sources', 'detail'] }),
        query_client.invalidateQueries({ queryKey: ['kb', 'sources', 'paragraphs'] }),
        query_client.invalidateQueries({ queryKey: ['kb', 'graph'] }),
        query_client.invalidateQueries({ queryKey: kb_query_keys.manual_relations() }),
      ]);
    },
    onError: (source_error) => {
      set_error((source_error as Error).message);
    },
  });

  async function save_source(
    source_id: string,
    payload: {
      name?: string;
      summary?: string;
      metadata?: Record<string, unknown>;
    },
  ): Promise<void> {
    await update_source_mutation.mutateAsync({ source_id, ...payload });
  }

  async function remove_source(source_id: string): Promise<void> {
    await delete_source_mutation.mutateAsync(source_id);
  }

  useEffect(() => {
    if (sources_query.error) {
      set_error((sources_query.error as Error).message);
    }
  }, [set_error, sources_query.error]);

  useEffect(() => {
    if (source_detail_query.error) {
      set_error((source_detail_query.error as Error).message);
    }
  }, [set_error, source_detail_query.error]);

  useEffect(() => {
    if (source_paragraphs_query.error) {
      set_error((source_paragraphs_query.error as Error).message);
    }
  }, [set_error, source_paragraphs_query.error]);

  useEffect(() => {
    const sources = sources_query.data ?? [];
    if (active_workspace !== 'chat' || !is_source_library_open || selected_source_browser_id || !sources.length) {
      return;
    }
    set_selected_source_browser_id(sources[0].id);
  }, [active_workspace, is_source_library_open, selected_source_browser_id, sources_query.data]);

  useEffect(() => {
    const sources = sources_query.data ?? [];
    if (!selected_source_browser_id) {
      return;
    }
    if (sources.some((source) => source.id === selected_source_browser_id)) {
      return;
    }
    set_selected_source_browser_id(sources[0]?.id ?? null);
  }, [selected_source_browser_id, sources_query.data]);

  return {
    sources: (sources_query.data ?? []) as SourceRecord[],
    refresh_sources,
    update_source: save_source,
    delete_source: remove_source,
    selected_source_browser_id,
    set_selected_source_browser_id,
    source_detail: (source_detail_query.data ?? null) as SourceDetailRecord | null,
    source_paragraphs: (source_paragraphs_query.data ?? []) as ParagraphRecord[],
    is_updating_source: update_source_mutation.isPending,
    is_deleting_source: delete_source_mutation.isPending,
  };
}
