/**
 * Graph, manual-relation, selection, and highlight state.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';

import {
  create_manual_relation,
  delete_manual_relation,
  fetch_graph,
  get_graph_edge_detail,
  get_graph_node_detail,
  list_manual_relations,
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
    const graph = graph_query.data ?? { nodes: [], edges: [] };
    if (selected_node_id && !has_node(graph, selected_node_id)) {
      set_selected_node_id(null);
    }
    if (selected_edge_id && !has_edge(graph, selected_edge_id)) {
      set_selected_edge_id(null);
    }
  }, [graph_query.data, selected_edge_id, selected_node_id]);

  return {
    graph: (graph_query.data ?? { nodes: [], edges: [] }) as KnowledgeGraphRecord,
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
    highlighted_node_ids,
    set_highlighted_node_ids,
    highlighted_edge_ids,
    set_highlighted_edge_ids,
    is_graph_loading: graph_query.isFetching,
    is_creating_manual_relation: create_relation_mutation.isPending,
    create_relation,
    remove_manual_relation,
  };
}
