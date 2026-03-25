/**
 * Query-studio workspace slice.
 */

import { use_knowledge_base_workspace_context } from '../../shared/context/knowledge_base_workspace_context';

export function use_query_studio() {
  const workspace = use_knowledge_base_workspace_context();

  return {
    query_mode: workspace.query_mode,
    answer_result: workspace.answer_result,
    record_results: workspace.record_results,
    entity_results: workspace.entity_results,
    relation_results: workspace.relation_results,
    source_results: workspace.source_results,
    is_querying: workspace.is_querying,
    set_query_mode: workspace.set_query_mode,
    execute_query: workspace.execute_query,
    focus_entity: workspace.focus_entity,
    focus_relation: workspace.focus_relation,
    focus_source: workspace.focus_source,
    focus_paragraph: workspace.focus_paragraph,
  };
}
