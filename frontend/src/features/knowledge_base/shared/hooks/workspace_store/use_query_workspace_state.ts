/**
 * Query execution and query-result state.
 */

import { startTransition, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';

import { QUERY_MODE_LABELS } from '../../config/ui_constants';
import {
  create_chat_session,
  get_chat_session,
  list_chat_sessions,
  post_chat_message,
  search_entities,
  search_records,
  search_relations,
  search_sources,
} from '../../api/query_api';
import type {
  AnswerExecutionRecord,
  ChatMessageRecord,
  ChatSessionDetailRecord,
  ChatSessionRecord,
  EntitySearchItemRecord,
  QueryMode,
  RecordSearchItemRecord,
  RelationSearchItemRecord,
  SourceSearchItemRecord,
  WorkspaceTab,
} from '../../types/knowledge_base_types';

interface QueryWorkspaceStateProps {
  active_workspace: WorkspaceTab;
  query_mode: QueryMode;
  selected_source_ids: string[];
  set_active_workspace: Dispatch<SetStateAction<WorkspaceTab>>;
  set_last_query_text: Dispatch<SetStateAction<string>>;
  set_message: Dispatch<SetStateAction<string>>;
  set_error: Dispatch<SetStateAction<string | null>>;
  set_highlighted_node_ids: Dispatch<SetStateAction<string[]>>;
  set_highlighted_edge_ids: Dispatch<SetStateAction<string[]>>;
}

const DEFAULT_SESSION_TITLE = '新对话';

function resolve_answer_execution(message: ChatMessageRecord | null): AnswerExecutionRecord {
  if (message?.execution) {
    return message.execution;
  }
  return {
    status: 'idle',
    retrieval_mode: 'none',
    model_invoked: false,
    matched_paragraph_count: 0,
    message: '等待执行问答。',
  };
}

function build_answer_message(message: ChatMessageRecord): string {
  const execution = resolve_answer_execution(message);
  if (execution.model_invoked) {
    return `问答完成，系统已基于 ${execution.matched_paragraph_count} 条证据生成回答。`;
  }
  return execution.message;
}

function latest_assistant_message(messages: ChatMessageRecord[]): ChatMessageRecord | null {
  const assistant_messages = messages.filter((message) => message.role === 'assistant');
  return assistant_messages.length ? assistant_messages[assistant_messages.length - 1] : null;
}

export function use_query_workspace_state(props: QueryWorkspaceStateProps) {
  const {
    active_workspace,
    query_mode,
    selected_source_ids,
    set_active_workspace,
    set_last_query_text,
    set_message,
    set_error,
    set_highlighted_node_ids,
    set_highlighted_edge_ids,
  } = props;

  const [answer_sessions, set_answer_sessions] = useState<ChatSessionRecord[]>([]);
  const [active_answer_session_id, set_active_answer_session_id] = useState<string | null>(null);
  const [answer_messages, set_answer_messages] = useState<ChatMessageRecord[]>([]);
  const [record_results, set_record_results] = useState<RecordSearchItemRecord[]>([]);
  const [entity_results, set_entity_results] = useState<EntitySearchItemRecord[]>([]);
  const [relation_results, set_relation_results] = useState<RelationSearchItemRecord[]>([]);
  const [source_results, set_source_results] = useState<SourceSearchItemRecord[]>([]);
  const [is_querying, set_is_querying] = useState<boolean>(false);
  const [has_hydrated_answer_sessions, set_has_hydrated_answer_sessions] = useState<boolean>(false);
  const [is_loading_answer_sessions, set_is_loading_answer_sessions] = useState<boolean>(false);
  const hydrate_answer_sessions_ref = useRef<Promise<void> | null>(null);
  const active_answer_message: ChatMessageRecord | null = latest_assistant_message(answer_messages);

  async function apply_session_detail(detail: ChatSessionDetailRecord): Promise<void> {
    const latest_answer_message = latest_assistant_message(detail.messages);
    startTransition(() => {
      set_active_answer_session_id(detail.session.id);
      set_answer_messages(detail.messages);
      set_highlighted_node_ids(latest_answer_message?.highlighted_node_ids ?? []);
      set_highlighted_edge_ids(latest_answer_message?.highlighted_edge_ids ?? []);
    });
  }

  async function hydrate_answer_sessions(preferred_session_id?: string | null): Promise<void> {
    if (hydrate_answer_sessions_ref.current && !preferred_session_id) {
      await hydrate_answer_sessions_ref.current;
      return;
    }
    if (has_hydrated_answer_sessions && !preferred_session_id) {
      return;
    }

    const hydrate_promise = (async () => {
      set_is_loading_answer_sessions(true);
      const sessions = await list_chat_sessions();
      startTransition(() => {
        set_answer_sessions(sessions);
      });
      const next_session_id = preferred_session_id ?? active_answer_session_id ?? sessions[0]?.id ?? null;
      if (!next_session_id) {
        startTransition(() => {
          set_active_answer_session_id(null);
          set_answer_messages([]);
          set_highlighted_node_ids([]);
          set_highlighted_edge_ids([]);
        });
        set_has_hydrated_answer_sessions(true);
        return;
      }
      const detail = await get_chat_session(next_session_id);
      await apply_session_detail(detail);
      set_has_hydrated_answer_sessions(true);
    })();

    hydrate_answer_sessions_ref.current = hydrate_promise;
    try {
      await hydrate_promise;
    } finally {
      hydrate_answer_sessions_ref.current = null;
      set_is_loading_answer_sessions(false);
    }
  }

  async function ensure_answer_sessions_ready(): Promise<void> {
    await hydrate_answer_sessions();
  }

  async function ensure_active_session(): Promise<string> {
    if (active_answer_session_id) {
      return active_answer_session_id;
    }
    const created = await create_chat_session({
      title: DEFAULT_SESSION_TITLE,
      metadata: { source_ids: selected_source_ids },
    });
    startTransition(() => {
      set_answer_sessions((current_sessions) => [created, ...current_sessions.filter((item) => item.id !== created.id)]);
      set_active_answer_session_id(created.id);
    });
    return created.id;
  }

  async function select_answer_session(session_id: string): Promise<void> {
    const detail = await get_chat_session(session_id);
    await apply_session_detail(detail);
  }

  async function create_answer_session(): Promise<void> {
    try {
      const session = await create_chat_session({
        title: DEFAULT_SESSION_TITLE,
        metadata: { source_ids: selected_source_ids },
      });
      startTransition(() => {
        set_answer_sessions((current_sessions) => [session, ...current_sessions.filter((item) => item.id !== session.id)]);
        set_active_answer_session_id(session.id);
        set_answer_messages([]);
        set_highlighted_node_ids([]);
        set_highlighted_edge_ids([]);
      });
      set_has_hydrated_answer_sessions(true);
      set_message(`已创建会话：${session.title}`);
      set_error(null);
    } catch (session_error) {
      set_error((session_error as Error).message);
    }
  }

  useEffect(() => {
    if (active_workspace !== 'chat' || query_mode !== 'answer' || has_hydrated_answer_sessions) {
      return;
    }
    void hydrate_answer_sessions().catch((session_error) => {
      set_error((session_error as Error).message);
    });
  }, [active_workspace, query_mode, has_hydrated_answer_sessions, set_error]);

  async function execute_query(query_text: string): Promise<void> {
    const normalized_query = query_text.trim();
    if (!normalized_query) {
      return;
    }

    let answer_session_id: string | null = null;

    set_is_querying(true);
    set_last_query_text(normalized_query);
    set_active_workspace('chat');
    set_error(null);
    set_message(`正在执行${QUERY_MODE_LABELS[query_mode]}...`);

    try {
      if (query_mode === 'answer') {
        set_record_results([]);
        set_entity_results([]);
        set_relation_results([]);
        set_source_results([]);

        await ensure_answer_sessions_ready();
        const session_id = await ensure_active_session();
        answer_session_id = session_id;
        const detail = await post_chat_message(session_id, {
          content: normalized_query,
          source_ids: selected_source_ids.length ? selected_source_ids : undefined,
          top_k: 6,
        });
        await apply_session_detail(detail);
        startTransition(() => {
          set_answer_sessions((current_sessions) => {
            const next_session = detail.session;
            return [next_session, ...current_sessions.filter((item) => item.id !== next_session.id)];
          });
        });
        const latest_answer_message = latest_assistant_message(detail.messages);
        if (latest_answer_message) {
          set_message(build_answer_message(latest_answer_message));
        }
        set_error(null);
        return;
      }

      if (query_mode === 'record') {
        set_entity_results([]);
        set_relation_results([]);
        set_source_results([]);
        const items = await search_records({
          query: normalized_query,
          source_ids: selected_source_ids.length ? selected_source_ids : undefined,
          limit: 20,
        });
        startTransition(() => {
          set_record_results(items);
          set_message(`记录检索完成，共 ${items.length} 条结果。`);
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
      if (query_mode === 'answer' && answer_session_id) {
        try {
          const detail = await get_chat_session(answer_session_id);
          await apply_session_detail(detail);
        } catch {
          // Ignore refresh failures and surface the original request error.
        }
      }
      set_error((query_error as Error).message);
    } finally {
      set_is_querying(false);
    }
  }

  return {
    answer_sessions,
    active_answer_session_id,
    answer_messages,
    active_answer_message,
    record_results,
    entity_results,
    relation_results,
    source_results,
    is_querying,
    is_loading_answer_sessions,
    execute_query,
    select_answer_session,
    create_answer_session,
  };
}
