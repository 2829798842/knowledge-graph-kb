/**
 * Query execution and query-result state.
 */

import { startTransition, useState, type Dispatch, type SetStateAction } from 'react';

import { QUERY_MODE_LABELS } from '../../config/ui_constants';
import {
  answer_query,
  search_entities,
  search_records,
  search_relations,
  search_sources,
} from '../../api/query_api';
import type {
  AnswerQueryResult,
  EntitySearchItemRecord,
  QueryMode,
  RecordSearchItemRecord,
  RelationSearchItemRecord,
  SourceSearchItemRecord,
  WorkspaceTab,
} from '../../types/knowledge_base_types';

interface QueryWorkspaceStateProps {
  query_mode: QueryMode;
  selected_source_ids: string[];
  set_active_workspace: Dispatch<SetStateAction<WorkspaceTab>>;
  set_last_query_text: Dispatch<SetStateAction<string>>;
  set_message: Dispatch<SetStateAction<string>>;
  set_error: Dispatch<SetStateAction<string | null>>;
  set_highlighted_node_ids: Dispatch<SetStateAction<string[]>>;
  set_highlighted_edge_ids: Dispatch<SetStateAction<string[]>>;
}

export function use_query_workspace_state(props: QueryWorkspaceStateProps) {
  const {
    query_mode,
    selected_source_ids,
    set_active_workspace,
    set_last_query_text,
    set_message,
    set_error,
    set_highlighted_node_ids,
    set_highlighted_edge_ids,
  } = props;

  const [answer_result, set_answer_result] = useState<AnswerQueryResult | null>(null);
  const [record_results, set_record_results] = useState<RecordSearchItemRecord[]>([]);
  const [entity_results, set_entity_results] = useState<EntitySearchItemRecord[]>([]);
  const [relation_results, set_relation_results] = useState<RelationSearchItemRecord[]>([]);
  const [source_results, set_source_results] = useState<SourceSearchItemRecord[]>([]);
  const [is_querying, set_is_querying] = useState<boolean>(false);

  async function execute_query(query_text: string): Promise<void> {
    const normalized_query: string = query_text.trim();
    if (!normalized_query) {
      return;
    }

    set_is_querying(true);
    set_last_query_text(normalized_query);
    set_active_workspace('query');
    set_error(null);
    set_message(`正在执行${QUERY_MODE_LABELS[query_mode]}...`);

    try {
      if (query_mode === 'answer') {
        set_record_results([]);
        set_entity_results([]);
        set_relation_results([]);
        set_source_results([]);

        const result = await answer_query({
          query: normalized_query,
          source_ids: selected_source_ids.length ? selected_source_ids : undefined,
          exact_first: true,
          top_k: 6,
        });
        startTransition(() => {
          set_answer_result(result);
          set_highlighted_node_ids(result.highlighted_node_ids);
          set_highlighted_edge_ids(result.highlighted_edge_ids);
          set_message('问答完成，图谱高亮已同步。');
          set_error(null);
        });
        return;
      }

      set_answer_result(null);

      if (query_mode === 'record') {
        set_entity_results([]);
        set_relation_results([]);
        set_source_results([]);
        const items = await search_records({
          query: normalized_query,
          source_ids: selected_source_ids.length ? selected_source_ids : undefined,
          limit: 20,
          mode: 'exact_first',
        });
        startTransition(() => {
          set_record_results(items);
          set_message(`表格记录检索完成，共 ${items.length} 条结果。`);
          set_error(null);
        });
        return;
      }

      set_record_results([]);

      if (query_mode === 'entity') {
        set_relation_results([]);
        set_source_results([]);
        const items = await search_entities({ query: normalized_query, limit: 20 });
        startTransition(() => {
          set_entity_results(items);
          set_message(`实体检索完成，共 ${items.length} 条结果。`);
          set_error(null);
        });
        return;
      }

      set_entity_results([]);

      if (query_mode === 'relation') {
        set_source_results([]);
        const items = await search_relations({ query: normalized_query, limit: 20 });
        startTransition(() => {
          set_relation_results(items);
          set_message(`关系检索完成，共 ${items.length} 条结果。`);
          set_error(null);
        });
        return;
      }

      set_relation_results([]);
      const items = await search_sources({ query: normalized_query, limit: 20 });
      startTransition(() => {
        set_source_results(items);
        set_message(`来源检索完成，共 ${items.length} 条结果。`);
        set_error(null);
      });
    } catch (query_error) {
      set_error((query_error as Error).message);
    } finally {
      set_is_querying(false);
    }
  }

  return {
    answer_result,
    record_results,
    entity_results,
    relation_results,
    source_results,
    is_querying,
    execute_query,
  };
}
