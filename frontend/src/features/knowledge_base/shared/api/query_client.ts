import { QueryClient } from '@tanstack/react-query';

export const kb_query_client = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: false,
    },
  },
});

export const kb_query_keys = {
  model_config: () => ['kb', 'config', 'model'] as const,
  graph: (params: { source_ids: string[]; include_paragraphs: boolean; density: number }) =>
    ['kb', 'graph', params] as const,
  manual_relations: () => ['kb', 'graph', 'manual-relations'] as const,
  node_detail: (node_id: string | null) => ['kb', 'graph', 'node-detail', node_id] as const,
  edge_detail: (edge_id: string | null) => ['kb', 'graph', 'edge-detail', edge_id] as const,
  import_jobs: () => ['kb', 'imports', 'jobs'] as const,
  source_list: () => ['kb', 'sources'] as const,
  source_detail: (source_id: string | null) => ['kb', 'sources', 'detail', source_id] as const,
  source_paragraphs: (source_id: string | null) => ['kb', 'sources', 'paragraphs', source_id] as const,
};
