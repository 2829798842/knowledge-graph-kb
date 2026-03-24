/**
 * 模块名称：features/knowledge_base/hooks/use_knowledge_base
 * 主要功能：管理知识库工作台的前端状态、任务轮询与数据同步。
 */

import { useEffect, useMemo, useState } from 'react';

import {
  create_manual_edge,
  delete_edge,
  fetch_documents,
  fetch_graph,
  fetch_job,
  fetch_jobs,
  fetch_model_configuration,
  run_query,
  start_document_extraction as request_document_extraction,
  test_model_configuration,
  update_model_configuration,
  upload_document,
} from '../api/knowledge_base_api';
import { EMPTY_GRAPH, INITIAL_STATUS_MESSAGE, JOB_POLL_INTERVAL_MS } from '../constants/knowledge_base_constants';
import type {
  GraphEdgeRecord,
  GraphNodeRecord,
  GraphPayload,
  KnowledgeBaseDocument,
  KnowledgeBaseJob,
  ModelConfiguration,
  ModelConfigurationTestRequest,
  ModelConfigurationTestResult,
  ModelConfigurationUpdateRequest,
  QueryResult,
} from '../types/knowledge_base';
import {
  read_documents_cache,
  read_graph_cache,
  read_model_configuration_cache,
  read_workspace_preferences,
  write_documents_cache,
  write_graph_cache,
  write_model_configuration_cache,
  write_workspace_preferences,
} from '../utils/cache_utils';
import { get_active_job_ids, merge_jobs } from '../utils/job_utils';

export interface UseKnowledgeBaseResult {
  documents: KnowledgeBaseDocument[];
  jobs: KnowledgeBaseJob[];
  graph: GraphPayload;
  model_configuration: ModelConfiguration | null;
  model_configuration_test_result: ModelConfigurationTestResult | null;
  selected_document_id: string | null;
  include_chunks: boolean;
  is_graph_loading: boolean;
  is_model_config_loading: boolean;
  is_model_config_saving: boolean;
  is_model_config_testing: boolean;
  is_starting_extraction: boolean;
  starting_document_id: string | null;
  selected_node: GraphNodeRecord | null;
  selected_edge: GraphEdgeRecord | null;
  source_node_id: string;
  target_node_id: string;
  query: string;
  query_result: QueryResult | null;
  message: string;
  error: string | null;
  is_uploading: boolean;
  is_querying: boolean;
  highlighted_node_ids: string[];
  highlighted_edge_ids: string[];
  set_selected_document_id: (document_id: string | null) => void;
  set_include_chunks: (value: boolean) => void;
  set_source_node_id: (node_id: string) => void;
  set_target_node_id: (node_id: string) => void;
  set_query: (value: string) => void;
  select_node: (node: GraphNodeRecord) => void;
  select_edge: (edge: GraphEdgeRecord) => void;
  clear_selection: () => void;
  upload_file: (file: File) => Promise<void>;
  start_document_extraction: (document_id?: string | null) => Promise<void>;
  submit_query: () => Promise<void>;
  create_edge: () => Promise<void>;
  remove_selected_edge: () => Promise<void>;
  save_model_configuration: (payload: ModelConfigurationUpdateRequest) => Promise<void>;
  run_model_configuration_test: (payload: ModelConfigurationTestRequest) => Promise<void>;
}

export function use_knowledge_base(): UseKnowledgeBaseResult {
  const initial_preferences = useMemo(() => read_workspace_preferences(), []);
  const initial_documents = useMemo(() => read_documents_cache(), []);
  const initial_model_configuration = useMemo(() => read_model_configuration_cache(), []);
  const initial_graph = useMemo(
    () => read_graph_cache(initial_preferences.selected_document_id, initial_preferences.include_chunks),
    [initial_preferences.include_chunks, initial_preferences.selected_document_id],
  );

  const [documents, set_documents] = useState<KnowledgeBaseDocument[]>(initial_documents);
  const [jobs, set_jobs] = useState<KnowledgeBaseJob[]>([]);
  const [graph, set_graph] = useState<GraphPayload>(initial_graph);
  const [model_configuration, set_model_configuration] = useState<ModelConfiguration | null>(initial_model_configuration);
  const [model_configuration_test_result, set_model_configuration_test_result] =
    useState<ModelConfigurationTestResult | null>(null);
  const [selected_document_id, set_selected_document_id] = useState<string | null>(
    initial_preferences.selected_document_id,
  );
  const [include_chunks, set_include_chunks] = useState<boolean>(initial_preferences.include_chunks);
  const [is_graph_loading, set_is_graph_loading] = useState<boolean>(false);
  const [is_model_config_loading, set_is_model_config_loading] = useState<boolean>(false);
  const [is_model_config_saving, set_is_model_config_saving] = useState<boolean>(false);
  const [is_model_config_testing, set_is_model_config_testing] = useState<boolean>(false);
  const [is_starting_extraction, set_is_starting_extraction] = useState<boolean>(false);
  const [starting_document_id, set_starting_document_id] = useState<string | null>(null);
  const [selected_node, set_selected_node] = useState<GraphNodeRecord | null>(null);
  const [selected_edge, set_selected_edge] = useState<GraphEdgeRecord | null>(null);
  const [source_node_id, set_source_node_id] = useState<string>('');
  const [target_node_id, set_target_node_id] = useState<string>('');
  const [query, set_query] = useState<string>('');
  const [query_result, set_query_result] = useState<QueryResult | null>(null);
  const [message, set_message] = useState<string>(() => {
    if (initial_documents.length || initial_graph.nodes.length || initial_graph.edges.length) {
      return '已从本地缓存恢复上次工作区，正在同步最新数据。';
    }
    return INITIAL_STATUS_MESSAGE;
  });
  const [error, set_error] = useState<string | null>(null);
  const [is_uploading, set_is_uploading] = useState<boolean>(false);
  const [is_querying, set_is_querying] = useState<boolean>(false);
  const active_job_ids: string[] = useMemo(() => get_active_job_ids(jobs), [jobs]);
  const highlighted_node_ids: string[] = useMemo(
    () => query_result?.ranked_nodes.map((node) => node.id) ?? [],
    [query_result],
  );
  const highlighted_edge_ids: string[] = useMemo(
    () => query_result?.ranked_edges.map((edge) => edge.id) ?? [],
    [query_result],
  );

  useEffect(() => {
    void refresh_documents();
    void refresh_jobs();
    void refresh_model_configuration();
  }, []);

  useEffect(() => {
    write_workspace_preferences({ selected_document_id, include_chunks });
  }, [include_chunks, selected_document_id]);

  useEffect(() => {
    const cached_graph: GraphPayload = read_graph_cache(selected_document_id, include_chunks);
    set_graph(cached_graph);
    set_selected_node((current_node) =>
      current_node && cached_graph.nodes.some((node) => node.id === current_node.id) ? current_node : null,
    );
    set_selected_edge((current_edge) =>
      current_edge && cached_graph.edges.some((edge) => edge.id === current_edge.id) ? current_edge : null,
    );

    if (cached_graph.nodes.length || cached_graph.edges.length) {
      set_message('已加载本地图谱缓存，正在同步最新结果。');
    }

    void refresh_graph(selected_document_id, include_chunks);
  }, [include_chunks, selected_document_id]);

  useEffect(() => {
    if (!active_job_ids.length) {
      return;
    }

    const timer: number = window.setInterval(() => {
      void poll_jobs(active_job_ids);
    }, JOB_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [active_job_ids, include_chunks, selected_document_id]);

  async function refresh_documents(): Promise<void> {
    try {
      const response: KnowledgeBaseDocument[] = await fetch_documents();
      set_documents(response);
      write_documents_cache(response);
    } catch (request_error) {
      set_error((request_error as Error).message);
    }
  }

  async function refresh_jobs(): Promise<void> {
    try {
      const response: KnowledgeBaseJob[] = await fetch_jobs();
      set_jobs(response);
    } catch (request_error) {
      set_error((request_error as Error).message);
    }
  }

  async function refresh_graph(document_id: string | null, next_include_chunks: boolean): Promise<void> {
    set_is_graph_loading(true);
    try {
      const response: GraphPayload = await fetch_graph(document_id, next_include_chunks);
      set_graph(response);
      write_graph_cache(document_id, next_include_chunks, response);
      set_selected_node((current_node) =>
        current_node && response.nodes.some((node) => node.id === current_node.id) ? current_node : null,
      );
      set_selected_edge((current_edge) =>
        current_edge && response.edges.some((edge) => edge.id === current_edge.id) ? current_edge : null,
      );
    } catch (request_error) {
      set_error((request_error as Error).message);
    } finally {
      set_is_graph_loading(false);
    }
  }

  async function refresh_model_configuration(): Promise<void> {
    set_is_model_config_loading(true);
    try {
      const response: ModelConfiguration = await fetch_model_configuration();
      set_model_configuration(response);
      set_model_configuration_test_result(null);
      write_model_configuration_cache(response);
    } catch (request_error) {
      set_error((request_error as Error).message);
    } finally {
      set_is_model_config_loading(false);
    }
  }

  async function poll_jobs(job_ids: string[]): Promise<void> {
    try {
      const next_jobs: KnowledgeBaseJob[] = await Promise.all(job_ids.map((job_id) => fetch_job(job_id)));
      set_jobs((current_jobs) => merge_jobs(current_jobs, next_jobs));

      const failed_job: KnowledgeBaseJob | undefined = next_jobs.find((job) => job.status === 'failed');
      if (failed_job?.error_message) {
        set_error(failed_job.error_message);
      }

      const processing_job: KnowledgeBaseJob | undefined = next_jobs.find((job) => job.status === 'processing');
      if (processing_job?.status_message) {
        set_message(processing_job.status_message);
      }

      const completed_job: KnowledgeBaseJob | undefined = next_jobs.find((job) => job.status === 'completed');
      if (completed_job?.status_message) {
        set_message(completed_job.status_message);
      }

      if (next_jobs.some((job) => job.status === 'completed' || job.status === 'failed')) {
        await refresh_documents();
        await refresh_jobs();
        await refresh_graph(selected_document_id, include_chunks);
      }
    } catch (request_error) {
      set_error((request_error as Error).message);
    }
  }

  async function upload_file(file: File): Promise<void> {
    set_is_uploading(true);
    set_error(null);
    try {
      const response = await upload_document(file);
      set_selected_document_id(response.document_id);
      set_message(`已上传《${file.name}》，请点击“开始 LLM 抽取”继续处理。`);
      await refresh_documents();
      await refresh_jobs();
      await refresh_graph(response.document_id, include_chunks);
    } catch (request_error) {
      set_error((request_error as Error).message);
    } finally {
      set_is_uploading(false);
    }
  }

  async function start_document_extraction(document_id?: string | null): Promise<void> {
    const target_document_id: string | null = document_id ?? selected_document_id;
    if (!target_document_id) {
      set_error('请先选择一个文档，再开始抽取。');
      return;
    }

    set_is_starting_extraction(true);
    set_starting_document_id(target_document_id);
    set_error(null);
    try {
      const job: KnowledgeBaseJob = await request_document_extraction(target_document_id);
      set_jobs((current_jobs) => merge_jobs(current_jobs, [job]));
      set_message(job.status_message ?? '抽取任务已启动，处理进度会在下方实时更新。');
      await refresh_documents();
      await refresh_jobs();
    } catch (request_error) {
      set_error((request_error as Error).message);
    } finally {
      set_is_starting_extraction(false);
      set_starting_document_id(null);
    }
  }

  async function submit_query(): Promise<void> {
    if (!query.trim()) {
      return;
    }
    set_is_querying(true);
    set_error(null);
    try {
      const result: QueryResult = await run_query(query, selected_document_id ? [selected_document_id] : undefined);
      set_query_result(result);
      set_message('图谱排序已根据本次提问更新，高亮路径也已同步。');
    } catch (request_error) {
      set_error((request_error as Error).message);
    } finally {
      set_is_querying(false);
    }
  }

  async function create_edge(): Promise<void> {
    if (!source_node_id || !target_node_id || source_node_id === target_node_id) {
      set_error('请先选择两个不同的节点，再创建手工连边。');
      return;
    }
    set_error(null);
    try {
      await create_manual_edge(source_node_id, target_node_id);
      set_message('手工连边已创建，后续排序会考虑这条显式关系。');
      await refresh_graph(selected_document_id, include_chunks);
    } catch (request_error) {
      set_error((request_error as Error).message);
    }
  }

  async function remove_selected_edge(): Promise<void> {
    if (!selected_edge || selected_edge.type !== 'manual') {
      return;
    }
    set_error(null);
    try {
      await delete_edge(selected_edge.id);
      set_selected_edge(null);
      set_message('手工连边已删除。');
      await refresh_graph(selected_document_id, include_chunks);
    } catch (request_error) {
      set_error((request_error as Error).message);
    }
  }

  async function save_model_configuration(payload: ModelConfigurationUpdateRequest): Promise<void> {
    set_is_model_config_saving(true);
    set_error(null);
    try {
      const response: ModelConfiguration = await update_model_configuration(payload);
      set_model_configuration(response);
      set_model_configuration_test_result(null);
      write_model_configuration_cache(response);
      if (response.reindex_required) {
        set_query_result(null);
        await refresh_graph(selected_document_id, include_chunks);
      }
      set_message(response.notice ?? '模型配置已保存，新的导入与问答会使用最新设置。');
    } catch (request_error) {
      set_error((request_error as Error).message);
    } finally {
      set_is_model_config_saving(false);
    }
  }

  async function run_model_configuration_test(payload: ModelConfigurationTestRequest): Promise<void> {
    set_is_model_config_testing(true);
    set_error(null);
    try {
      const response: ModelConfigurationTestResult = await test_model_configuration(payload);
      set_model_configuration_test_result(response);
      set_message(response.message);
    } catch (request_error) {
      set_model_configuration_test_result(null);
      set_error((request_error as Error).message);
    } finally {
      set_is_model_config_testing(false);
    }
  }

  function select_node(node: GraphNodeRecord): void {
    set_selected_node(node);
    set_selected_edge(null);
  }

  function select_edge(edge: GraphEdgeRecord): void {
    set_selected_edge(edge);
    set_selected_node(null);
  }

  function clear_selection(): void {
    set_selected_node(null);
    set_selected_edge(null);
  }

  return {
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
  };
}
