/**
 * 模块名称：features/knowledge_base/components/knowledge_base_workspace
 * 主要功能：组合知识库界面的主工作区。
 */

import type { ResolvedTheme, ThemeMode } from '../../../theme';
import { use_knowledge_base } from '../hooks/use_knowledge_base';
import { GraphPanel, ImportPanel, ModelConfigPanel, QueryPanel } from './panels';
import { StatusBanner } from './status_banner';

interface KnowledgeBaseWorkspaceProps {
  theme_mode: ThemeMode;
  resolved_theme: ResolvedTheme;
  set_theme_mode: (theme_mode: ThemeMode) => void;
}

export function KnowledgeBaseWorkspace(props: KnowledgeBaseWorkspaceProps) {
  const { theme_mode, resolved_theme, set_theme_mode } = props;
  const {
    documents,
    jobs,
    graph,
    model_configuration,
    model_configuration_test_result,
    selected_document_id,
    include_chunks,
    is_graph_loading,
    is_model_config_loading,
    is_model_config_saving,
    is_model_config_testing,
    is_starting_extraction,
    starting_document_id,
    selected_node,
    selected_edge,
    source_node_id,
    target_node_id,
    query,
    query_result,
    message,
    error,
    is_uploading,
    is_querying,
    highlighted_node_ids,
    highlighted_edge_ids,
    set_selected_document_id,
    set_include_chunks,
    set_source_node_id,
    set_target_node_id,
    set_query,
    select_node,
    select_edge,
    clear_selection,
    upload_file,
    start_document_extraction,
    submit_query,
    create_edge,
    remove_selected_edge,
    save_model_configuration,
    run_model_configuration_test,
  } = use_knowledge_base();

  return (
    <main className='app-shell'>
      <StatusBanner
        message={message}
        error={error}
        document_count={documents.length}
        active_job_count={jobs.filter((job) => job.status === 'pending' || job.status === 'processing').length}
        node_count={graph.nodes.length}
        edge_count={graph.edges.length}
        highlighted_node_count={highlighted_node_ids.length}
        theme_mode={theme_mode}
        set_theme_mode={set_theme_mode}
      />

      <section className='workspace-grid'>
        <div className='panel-stack'>
          <ImportPanel
            documents={documents}
            jobs={jobs}
            selected_document_id={selected_document_id}
            include_chunks={include_chunks}
            is_uploading={is_uploading}
            is_starting_extraction={is_starting_extraction}
            starting_document_id={starting_document_id}
            set_selected_document_id={set_selected_document_id}
            set_include_chunks={set_include_chunks}
            upload_file={upload_file}
            start_document_extraction={start_document_extraction}
          />

          <ModelConfigPanel
            model_configuration={model_configuration}
            model_configuration_test_result={model_configuration_test_result}
            is_loading={is_model_config_loading}
            is_saving={is_model_config_saving}
            is_testing={is_model_config_testing}
            save_model_configuration={save_model_configuration}
            test_model_configuration={run_model_configuration_test}
          />
        </div>

        <GraphPanel
          graph={graph}
          is_graph_loading={is_graph_loading}
          selected_node={selected_node}
          selected_edge={selected_edge}
          source_node_id={source_node_id}
          target_node_id={target_node_id}
          highlighted_node_ids={highlighted_node_ids}
          highlighted_edge_ids={highlighted_edge_ids}
          resolved_theme={resolved_theme}
          set_source_node_id={set_source_node_id}
          set_target_node_id={set_target_node_id}
          select_node={select_node}
          select_edge={select_edge}
          clear_selection={clear_selection}
          create_edge={create_edge}
        />

        <QueryPanel
          query={query}
          selected_node={selected_node}
          selected_edge={selected_edge}
          query_result={query_result}
          is_querying={is_querying}
          set_query={set_query}
          submit_query={submit_query}
          remove_selected_edge={remove_selected_edge}
          highlighted_node_count={highlighted_node_ids.length}
          highlighted_edge_count={highlighted_edge_ids.length}
        />
      </section>
    </main>
  );
}
