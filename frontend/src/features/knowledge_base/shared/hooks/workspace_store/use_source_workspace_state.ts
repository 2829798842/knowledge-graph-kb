/**
 * Source catalog and source-browser state.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';

import { kb_query_keys } from '../../api/query_client';
import { get_source_detail, list_source_paragraphs, list_sources } from '../../api/source_api';
import type {
  ParagraphRecord,
  SourceDetailRecord,
  SourceRecord,
  WorkspaceTab,
} from '../../types/knowledge_base_types';

interface SourceWorkspaceStateProps {
  active_workspace: WorkspaceTab;
  set_error: Dispatch<SetStateAction<string | null>>;
}

export function use_source_workspace_state(props: SourceWorkspaceStateProps) {
  const { active_workspace, set_error } = props;
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
    if (active_workspace !== 'source' || selected_source_browser_id || !sources.length) {
      return;
    }
    set_selected_source_browser_id(sources[0].id);
  }, [active_workspace, selected_source_browser_id, sources_query.data]);

  return {
    sources: (sources_query.data ?? []) as SourceRecord[],
    refresh_sources,
    selected_source_browser_id,
    set_selected_source_browser_id,
    source_detail: (source_detail_query.data ?? null) as SourceDetailRecord | null,
    source_paragraphs: (source_paragraphs_query.data ?? []) as ParagraphRecord[],
  };
}
