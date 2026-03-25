/**
 * 问答与检索工作台状态切片。
 */

import { use_knowledge_base_workspace_context } from '../../shared/context/knowledge_base_workspace_context';

export function use_query_studio() {
  const workspace = use_knowledge_base_workspace_context();

  return {
    query_mode: workspace.query_mode,
    answer_sessions: workspace.answer_sessions,
    active_answer_session_id: workspace.active_answer_session_id,
    answer_messages: workspace.answer_messages,
    active_answer_message: workspace.active_answer_message,
    record_results: workspace.record_results,
    entity_results: workspace.entity_results,
    relation_results: workspace.relation_results,
    source_results: workspace.source_results,
    is_querying: workspace.is_querying,
    set_query_mode: workspace.set_query_mode,
    execute_query: workspace.execute_query,
    select_answer_session: workspace.select_answer_session,
    create_answer_session: workspace.create_answer_session,
    focus_entity: workspace.focus_entity,
    focus_relation: workspace.focus_relation,
    focus_source: workspace.focus_source,
    focus_paragraph: workspace.focus_paragraph,
  };
}
