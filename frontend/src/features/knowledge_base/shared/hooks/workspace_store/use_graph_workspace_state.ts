/**
 * Graph, manual-relation, selection, and highlight state.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';

import {
  create_graph_node,
  create_manual_relation,
  delete_graph_edge,
  delete_graph_node,
  delete_manual_relation,
  fetch_graph,
  get_graph_edge_detail,
  get_graph_node_detail,
  list_manual_relations,
  update_graph_node,
} from '../../api/graph_api';
import { kb_query_keys } from '../../api/query_client';
import type {
  GraphEdgeDetailRecord,
  GraphNodeDetailRecord,
  KnowledgeGraphRecord,
  ManualRelationRecord,
} from '../../types/knowledge_base_types';

function has_node(graph: KnowledgeGraphRecord, node_id: string): boolean {
  return graph.nodes.some((node) => node.id === node_id);
}

function has_edge(graph: KnowledgeGraphRecord, edge_id: string): boolean {
  return graph.edges.some((edge) => edge.id === edge_id);
}

const EMPTY_GRAPH: KnowledgeGraphRecord = { nodes: [], edges: [] };

interface NormalizedGraphState {
  graph: KnowledgeGraphRecord;
  dropped_edge_count: number;
}

function normalize_graph(graph: KnowledgeGraphRecord): NormalizedGraphState {
  const normalized_nodes = Array.isArray(graph.nodes) ? graph.nodes.filter(Boolean) : [];
  const visible_node_ids = new Set(normalized_nodes.map((node) => node.id));
  const normalized_edges = [];
  let dropped_edge_count = 0;

  for (const edge of Array.isArray(graph.edges) ? graph.edges : []) {
    if (!edge || !visible_node_ids.has(edge.source) || !visible_node_ids.has(edge.target)) {
      dropped_edge_count += 1;
      continue;
    }
    normalized_edges.push(edge);
  }

  return {
    graph: {
      nodes: normalized_nodes,
      edges: normalized_edges,
    },
    dropped_edge_count,
  };
}

interface GraphWorkspaceStateProps {
  default_graph_density: number;
  set_message: Dispatch<SetStateAction<string>>;
  set_error: Dispatch<SetStateAction<string | null>>;
}

export function use_graph_workspace_state(props: GraphWorkspaceStateProps) {
  const { default_graph_density, set_message, set_error } = props;
  const query_client = useQueryClient();
  const [selected_source_ids, set_selected_source_ids] = useState<string[]>([]);
  const [include_paragraphs, set_include_paragraphs] = useState<boolean>(true);
  const [density, set_density] = useState<number>(default_graph_density);
  const [selected_node_id, set_selected_node_id] = useState<string | null>(null);
  const [selected_edge_id, set_selected_edge_id] = useState<string | null>(null);
  const [highlighted_node_ids, set_highlighted_node_ids] = useState<string[]>([]);
  const [highlighted_edge_ids, set_highlighted_edge_ids] = useState<string[]>([]);

  const graph_query = useQuery({
    queryKey: kb_query_keys.graph({ source_ids: selected_source_ids, include_paragraphs, density }),
    queryFn: () =>
      fetch_graph({
        source_ids: selected_source_ids,
        include_paragraphs,
        density,
      }),
  });

  const manual_relations_query = useQuery({
    queryKey: kb_query_keys.manual_relations(),
    queryFn: list_manual_relations,
  });

  const node_detail_query = useQuery({
    queryKey: kb_query_keys.node_detail(selected_node_id),
    queryFn: () => get_graph_node_detail(selected_node_id!),
    enabled: Boolean(selected_node_id),
  });

  const edge_detail_query = useQuery({
    queryKey: kb_query_keys.edge_detail(selected_edge_id),
    queryFn: () => get_graph_edge_detail(selected_edge_id!),
    enabled: Boolean(selected_edge_id),
  });

  const normalized_graph_state = useMemo<NormalizedGraphState>(
    () => normalize_graph((graph_query.data ?? EMPTY_GRAPH) as KnowledgeGraphRecord),
    [graph_query.data],
  );
  const graph = normalized_graph_state.graph;
  const graph_error_message =
    (graph_query.error as Error | null)?.message ??
    (manual_relations_query.error as Error | null)?.message ??
    (node_detail_query.error as Error | null)?.message ??
    (edge_detail_query.error as Error | null)?.message ??
    null;

  async function refresh_graph(): Promise<void> {
    try {
      await query_client.invalidateQueries({ queryKey: ['kb', 'graph'] });
    } catch (refresh_error) {
      set_error((refresh_error as Error).message);
    }
  }

  async function refresh_manual_relations(): Promise<void> {
    try {
      await query_client.invalidateQueries({ queryKey: kb_query_keys.manual_relations() });
    } catch (refresh_error) {
      set_error((refresh_error as Error).message);
    }
  }

  async function refresh_graph_details(): Promise<void> {
    try {
      await Promise.all([
        query_client.invalidateQueries({ queryKey: ['kb', 'graph', 'node-detail'] }),
        query_client.invalidateQueries({ queryKey: ['kb', 'graph', 'edge-detail'] }),
      ]);
    } catch (refresh_error) {
      set_error((refresh_error as Error).message);
    }
  }

  async function refresh_source_queries(): Promise<void> {
    try {
      await Promise.all([
        query_client.invalidateQueries({ queryKey: kb_query_keys.source_list() }),
        query_client.invalidateQueries({ queryKey: ['kb', 'sources', 'detail'] }),
        query_client.invalidateQueries({ queryKey: ['kb', 'sources', 'paragraphs'] }),
      ]);
    } catch (refresh_error) {
      set_error((refresh_error as Error).message);
    }
  }

  const create_node_mutation = useMutation({
    mutationFn: (payload: { label: string; description?: string; metadata?: Record<string, unknown> }) =>
      create_graph_node(payload),
    onSuccess: async (node) => {
      set_message(`已创建实体：${node.label}`);
      set_error(null);
      set_selected_node_id(node.id);
      set_selected_edge_id(null);
      set_highlighted_node_ids([node.id]);
      set_highlighted_edge_ids([]);
      await Promise.all([refresh_graph(), refresh_graph_details(), refresh_manual_relations()]);
    },
    onError: (graph_error) => {
      set_error((graph_error as Error).message);
    },
  });

  const create_relation_mutation = useMutation({
    mutationFn: (payload: {
      subject_node_id: string;
      predicate: string;
      object_node_id: string;
      weight: number;
    }) => create_manual_relation(payload),
    onSuccess: async () => {
      set_message('已创建手动关系。');
      set_error(null);
      await Promise.all([refresh_graph(), refresh_manual_relations()]);
    },
    onError: (relation_error) => {
      set_error((relation_error as Error).message);
    },
  });

  const remove_relation_mutation = useMutation({
    mutationFn: (relation_id: string) => delete_manual_relation(relation_id),
    onSuccess: async () => {
      set_message('已移除手动关系。');
      set_error(null);
      await Promise.all([refresh_graph(), refresh_manual_relations()]);
    },
    onError: (relation_error) => {
      set_error((relation_error as Error).message);
    },
  });

  const rename_node_mutation = useMutation({
    mutationFn: (payload: { node_id: string; label: string }) => update_graph_node(payload.node_id, { label: payload.label }),
    onSuccess: async () => {
      set_message('已更新节点名称。');
      set_error(null);
      await Promise.all([refresh_graph(), refresh_graph_details(), refresh_source_queries()]);
    },
    onError: (graph_error) => {
      set_error((graph_error as Error).message);
    },
  });

  const delete_node_mutation = useMutation({
    mutationFn: (node_id: string) => delete_graph_node(node_id),
    onSuccess: async (_result, node_id) => {
      set_selected_node_id((current) => (current === node_id ? null : current));
      set_highlighted_node_ids((current) => current.filter((item) => item !== node_id));
      if (node_id.startsWith('source:')) {
        const source_id = node_id.split(':')[1] ?? '';
        set_selected_source_ids((current) => current.filter((item) => item !== source_id));
      }
      set_message('已删除节点。');
      set_error(null);
      await Promise.all([refresh_graph(), refresh_manual_relations(), refresh_source_queries()]);
    },
    onError: (graph_error) => {
      set_error((graph_error as Error).message);
    },
  });

  const delete_edge_mutation = useMutation({
    mutationFn: (edge_id: string) => delete_graph_edge(edge_id),
    onSuccess: async (_result, edge_id) => {
      set_selected_edge_id((current) => (current === edge_id ? null : current));
      set_highlighted_edge_ids((current) => current.filter((item) => item !== edge_id));
      set_message('已删除关系。');
      set_error(null);
      await Promise.all([refresh_graph(), refresh_manual_relations(), refresh_source_queries()]);
    },
    onError: (graph_error) => {
      set_error((graph_error as Error).message);
    },
  });

  async function create_entity(
    label: string,
    options?: {
      description?: string;
      metadata?: Record<string, unknown>;
    },
  ): Promise<void> {
    await create_node_mutation.mutateAsync({
      label,
      description: options?.description,
      metadata: options?.metadata,
    });
  }

  async function create_relation(
    subject_node_id: string,
    predicate: string,
    object_node_id: string,
    weight: number,
  ): Promise<void> {
    await create_relation_mutation.mutateAsync({
      subject_node_id,
      predicate,
      object_node_id,
      weight,
    });
  }

  async function remove_manual_relation(relation_id: string): Promise<void> {
    await remove_relation_mutation.mutateAsync(relation_id);
  }

  async function rename_node(node_id: string, label: string): Promise<void> {
    await rename_node_mutation.mutateAsync({ node_id, label });
  }

  async function delete_node(node_id: string): Promise<void> {
    await delete_node_mutation.mutateAsync(node_id);
  }

  async function delete_edge(edge_id: string): Promise<void> {
    await delete_edge_mutation.mutateAsync(edge_id);
  }

  useEffect(() => {
    if (graph_query.error) {
      set_error((graph_query.error as Error).message);
    }
  }, [graph_query.error, set_error]);

  useEffect(() => {
    if (manual_relations_query.error) {
      set_error((manual_relations_query.error as Error).message);
    }
  }, [manual_relations_query.error, set_error]);

  useEffect(() => {
    if (node_detail_query.error) {
      set_error((node_detail_query.error as Error).message);
    }
  }, [node_detail_query.error, set_error]);

  useEffect(() => {
    if (edge_detail_query.error) {
      set_error((edge_detail_query.error as Error).message);
    }
  }, [edge_detail_query.error, set_error]);

  useEffect(() => {
    if (normalized_graph_state.dropped_edge_count <= 0) {
      return;
    }
    console.warn(`知识图谱已忽略 ${normalized_graph_state.dropped_edge_count} 条缺少端点节点的关系边。`);
  }, [normalized_graph_state.dropped_edge_count]);

  useEffect(() => {
    if (selected_node_id && !has_node(graph, selected_node_id)) {
      set_selected_node_id(null);
    }
    if (selected_edge_id && !has_edge(graph, selected_edge_id)) {
      set_selected_edge_id(null);
    }
  }, [graph, selected_edge_id, selected_node_id]);

  return {
    graph,
    refresh_graph,
    manual_relations: (manual_relations_query.data ?? []) as ManualRelationRecord[],
    refresh_manual_relations,
    selected_source_ids,
    set_selected_source_ids,
    include_paragraphs,
    set_include_paragraphs,
    density,
    set_density,
    selected_node_id,
    set_selected_node_id,
    selected_edge_id,
    set_selected_edge_id,
    node_detail: (node_detail_query.data ?? null) as GraphNodeDetailRecord | null,
    edge_detail: (edge_detail_query.data ?? null) as GraphEdgeDetailRecord | null,
    graph_error_message,
    highlighted_node_ids,
    set_highlighted_node_ids,
    highlighted_edge_ids,
    set_highlighted_edge_ids,
    is_graph_loading: graph_query.isFetching,
    is_creating_node: create_node_mutation.isPending,
    is_creating_manual_relation: create_relation_mutation.isPending,
    is_renaming_node: rename_node_mutation.isPending,
    is_deleting_node: delete_node_mutation.isPending,
    is_deleting_edge: delete_edge_mutation.isPending,
    create_entity,
    create_relation,
    remove_manual_relation,
    rename_node,
    delete_node,
    delete_edge,
  };
}
