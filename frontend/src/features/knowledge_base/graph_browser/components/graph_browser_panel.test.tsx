import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  GraphEdgeDetailRecord,
  GraphNodeDetailRecord,
  KnowledgeGraphRecord,
  SourceRecord,
} from '../../shared/types/knowledge_base_types';
import { GraphBrowserPanel } from './graph_browser_panel';

const select_node = vi.fn();
const select_edge = vi.fn();
const clear_graph_selection = vi.fn();
const clear_highlights = vi.fn();
const refresh_graph = vi.fn().mockResolvedValue(undefined);
const create_entity = vi.fn().mockResolvedValue(undefined);
const create_relation = vi.fn().mockResolvedValue(undefined);
const rename_node = vi.fn().mockResolvedValue(undefined);
const delete_node = vi.fn().mockResolvedValue(undefined);
const delete_edge = vi.fn().mockResolvedValue(undefined);
const set_selected_source_ids = vi.fn();
const set_include_paragraphs = vi.fn();
const set_density = vi.fn();
const reset_graph_filters = vi.fn();
const clear_source_filters = vi.fn();
const focus_source = vi.fn();
const focus_paragraph = vi.fn();
const focus_citation = vi.fn();

const graph: KnowledgeGraphRecord = {
  nodes: [
    {
      id: 'entity-fire-cat',
      type: 'entity',
      label: '火猫',
      display_label: '火猫',
      kind_label: '实体',
      source_name: '孙子兵法.txt',
      evidence_count: 2,
      size: 2,
      score: null,
      metadata: { relation_count: 1 },
    },
    {
      id: 'entity-fire-fox',
      type: 'entity',
      label: '火狐',
      display_label: '火狐',
      kind_label: '实体',
      source_name: '战术笔记.md',
      evidence_count: 1,
      size: 1,
      score: null,
      metadata: { relation_count: 1 },
    },
  ],
  edges: [
    {
      id: 'edge-1',
      source: 'entity-fire-cat',
      target: 'entity-fire-fox',
      type: 'relation',
      label: '关联',
      display_label: '关联',
      relation_kind_label: '抽取关系',
      source_name: '孙子兵法.txt',
      evidence_paragraph_id: 'paragraph-1',
      is_structural: false,
      weight: 0.9,
      metadata: {},
    },
  ],
};

const sources: SourceRecord[] = [
  {
    id: 'source-1',
    name: '孙子兵法.txt',
    source_kind: 'text',
    input_mode: 'upload',
    file_type: 'txt',
    storage_path: null,
    strategy: 'summary',
    status: 'ready',
    summary: '兵法原文',
    metadata: {},
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
  },
];

const node_detail: GraphNodeDetailRecord = {
  node: graph.nodes[0],
  source: { id: 'source-1', name: '孙子兵法.txt', summary: '兵法原文' },
  paragraphs: [
    {
      id: 'paragraph-1',
      paragraph_id: 'paragraph-1',
      source_id: 'source-1',
      source_name: '孙子兵法.txt',
      position: 12,
      content: '火猫相关段落',
    },
  ],
  relations: [
    {
      id: 'relation-1',
      label: '关联',
      metadata: { summary: '火猫与火狐有关联' },
    },
  ],
};

const edge_detail: GraphEdgeDetailRecord = {
  edge: graph.edges[0],
  source: { id: 'source-1', name: '孙子兵法.txt' },
  paragraph: {
    id: 'paragraph-1',
    paragraph_id: 'paragraph-1',
    source_id: 'source-1',
    source_name: '孙子兵法.txt',
    position: 12,
    content: '火猫与火狐相关段落',
  },
};

const browser_state = vi.hoisted(() => ({
  current: null as ReturnType<typeof createBrowserState> | null,
}));

function buildBrowserState() {
  return {
    graph,
    sources,
    manual_relations: [],
    selected_source_ids: [] as string[],
    include_paragraphs: false,
    density: 72,
    selected_node_id: null as string | null,
    selected_edge_id: null as string | null,
    node_detail: null as GraphNodeDetailRecord | null,
    edge_detail: null as GraphEdgeDetailRecord | null,
    graph_error_message: null as string | null,
    highlighted_node_ids: [] as string[],
    highlighted_edge_ids: [] as string[],
    is_graph_loading: false,
    is_creating_node: false,
    is_creating_manual_relation: false,
    is_renaming_node: false,
    is_deleting_node: false,
    is_deleting_edge: false,
    set_selected_source_ids,
    set_include_paragraphs,
    set_density,
    select_node,
    select_edge,
    clear_graph_selection,
    create_entity,
    create_relation,
    remove_manual_relation: vi.fn(),
    rename_node,
    delete_node,
    delete_edge,
    clear_highlights,
    refresh_graph,
    reset_graph_filters,
    clear_source_filters,
  };
}

function createBrowserState(overrides: Partial<ReturnType<typeof buildBrowserState>> = {}) {
  return { ...buildBrowserState(), ...overrides };
}

vi.mock('../hooks/use_graph_browser', () => ({
  use_graph_browser: () => browser_state.current,
}));

vi.mock('../../shared/context/knowledge_base_workspace_context', () => ({
  use_knowledge_base_workspace_context: () => ({
    focus_source,
    focus_paragraph,
    focus_citation,
  }),
}));

vi.mock('./pixi_knowledge_graph_canvas', () => ({
  PixiKnowledgeGraphCanvas: () => <div data-testid='pixi-canvas'>pixi-canvas</div>,
}));

describe('GraphBrowserPanel', () => {
  beforeEach(() => {
    browser_state.current = createBrowserState();
    vi.clearAllMocks();
  });

  it('uses quick switcher to choose a semantic node', async () => {
    const user = userEvent.setup();
    render(<GraphBrowserPanel resolved_theme='light' />);

    const input = screen.getByPlaceholderText('搜索实体名称、类型或来源');
    await user.click(input);
    await user.type(input, '火猫');

    expect(screen.getByRole('button', { name: /火猫/ })).toBeInTheDocument();
    await user.keyboard('{Enter}');

    expect(select_node).toHaveBeenCalledWith('entity-fire-cat');
  });

  it('shows local graph switch and node inspector summary blocks', async () => {
    const user = userEvent.setup();
    browser_state.current = createBrowserState({
      selected_node_id: 'entity-fire-cat',
      node_detail,
    });

    render(<GraphBrowserPanel resolved_theme='light' />);

    const local_button = screen.getByRole('button', { name: '局部图' });
    expect(local_button).toBeEnabled();

    expect(screen.getAllByText('属性').length).toBeGreaterThan(0);
    expect(screen.getByText('关系摘要')).toBeInTheDocument();
    expect(screen.getByText('证据入口')).toBeInTheDocument();

    await user.click(local_button);

    expect(local_button).toHaveAttribute('aria-pressed', 'true');
  });

  it('shows edge inspector summary blocks when an edge is selected', () => {
    browser_state.current = createBrowserState({
      selected_edge_id: 'edge-1',
      edge_detail,
    });

    render(<GraphBrowserPanel resolved_theme='light' />);

    expect(screen.getAllByText('属性').length).toBeGreaterThan(0);
    expect(screen.getByText('操作')).toBeInTheDocument();
    expect(screen.getByText('证据入口')).toBeInTheDocument();
  });

  it('exposes node evidence actions in the inspector second screen', async () => {
    const user = userEvent.setup();
    browser_state.current = createBrowserState({
      selected_node_id: 'entity-fire-cat',
      node_detail,
    });

    render(<GraphBrowserPanel resolved_theme='light' />);

    await user.click(screen.getByRole('button', { name: '定位段落' }));
    expect(focus_paragraph).toHaveBeenCalledWith('paragraph-1');

    await user.click(screen.getAllByRole('button', { name: '在来源中查看' })[0]);
    expect(focus_source).toHaveBeenCalledWith('source-1');

    await user.click(screen.getAllByRole('button', { name: '在图谱中高亮当前证据' })[0]);
    expect(focus_citation).toHaveBeenCalledWith('source-1', 'paragraph-1');
  });

  it('disambiguates duplicate source names in the current scope summary', async () => {
    const user = userEvent.setup();
    browser_state.current = createBrowserState({
      sources: [
        {
          ...sources[0],
          id: 'source-1111',
          name: '孙子兵法.txt',
        },
        {
          ...sources[0],
          id: 'source-2222',
          name: '孙子兵法.txt',
          summary: '重复导入的另一份来源',
        },
      ],
      selected_source_ids: ['source-1111', 'source-2222'],
    });

    render(<GraphBrowserPanel resolved_theme='light' />);

    expect(
      screen.getByText('当前范围：孙子兵法.txt · source-1、孙子兵法.txt · source-2'),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '筛选与显示' }));

    expect(screen.getByText('孙子兵法.txt · source-1')).toBeInTheDocument();
    expect(screen.getByText('孙子兵法.txt · source-2')).toBeInTheDocument();
  });
});
