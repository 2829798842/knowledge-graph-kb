import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FocusEvent,
  type FormEvent,
  type KeyboardEvent,
} from 'react';

import type { ResolvedTheme } from '../../../../theme';
import {
  GRAPH_VIEW_MODE_LABELS,
  GRAPH_VIEWPORT_MODE_LABELS,
  NODE_TYPE_LABELS,
  PREDICATE_SUGGESTIONS,
} from '../../shared/config/ui_constants';
import { use_knowledge_base_workspace_context } from '../../shared/context/knowledge_base_workspace_context';
import type {
  GraphDrawerMode,
  GraphLayerMode,
  GraphViewMode,
  GraphViewportMode,
  KnowledgeGraphEdgeRecord,
  KnowledgeGraphNodeRecord,
  LocalGraphState,
} from '../../shared/types/knowledge_base_types';
import { use_graph_browser } from '../hooks/use_graph_browser';
import { JsonDetails, MetadataRows } from './graph_browser_detail_blocks';
import {
  collect_edge_import_rows,
  collect_node_import_rows,
  create_search_candidate,
  create_viewport_command,
  DEFAULT_PREDICATE,
  DENSITY_PRESETS,
  edge_action_copy,
  format_source_display_name,
  GRAPH_LAYER_LABELS,
  node_action_copy,
  node_option_label,
  selected_source_summary,
  type GraphSearchCandidateRecord,
  type ViewportCommand,
} from './graph_browser_utils';
import { PixiKnowledgeGraphCanvas } from './pixi_knowledge_graph_canvas';
import { project_graph } from './graph_projection';
import '../styles/graph_browser_panel.css';

interface GraphBrowserPanelProps {
  resolved_theme: ResolvedTheme;
}

interface RelationDraft {
  subject_node_id: string;
  predicate: string;
  object_node_id: string;
  weight: number;
}

interface PreviewCardRecord {
  key: string;
  title: string;
  description: string;
  source_id?: string | null;
  paragraph_id?: string | null;
}

const DEFAULT_RELATION_DRAFT: RelationDraft = {
  subject_node_id: '',
  predicate: DEFAULT_PREDICATE,
  object_node_id: '',
  weight: 0.9,
};

const DEFAULT_LAYER_MODES: GraphLayerMode[] = ['semantic'];
const DEFAULT_LOCAL_GRAPH_STATE: LocalGraphState = {
  anchor_node_id: null,
  depth: 1,
};

function normalize_keyword(value: string): string {
  return value.trim().toLowerCase();
}

function is_entity_node(
  node: KnowledgeGraphNodeRecord | null | undefined,
): node is KnowledgeGraphNodeRecord {
  return Boolean(node && node.type === 'entity');
}

function is_left_drawer(mode: GraphDrawerMode): mode is 'filters' | 'create-node' | 'relation' {
  return mode === 'filters' || mode === 'create-node' || mode === 'relation';
}

function node_kind_label(node: KnowledgeGraphNodeRecord): string {
  return node.kind_label ?? NODE_TYPE_LABELS[node.type] ?? node.type;
}

function node_search_text(node: KnowledgeGraphNodeRecord): string {
  return [
    node.display_label ?? node.label,
    node_kind_label(node),
    node.source_name ?? '',
    node.id,
  ]
    .join(' ')
    .toLowerCase();
}

function edge_node_label(
  node_id: string,
  node_map: Map<string, KnowledgeGraphNodeRecord>,
): string {
  const node = node_map.get(node_id);
  return node?.display_label ?? node?.label ?? node_id;
}

function preview_text(value: Record<string, unknown>, fallback = '暂无更多信息'): string {
  const candidates = [
    value.content,
    value.excerpt,
    value.summary,
    value.display_label,
    value.label,
    value.name,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim();
    }
  }
  return fallback;
}

function to_record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function relation_summary_text(
  edge: KnowledgeGraphEdgeRecord,
  node_map: Map<string, KnowledgeGraphNodeRecord>,
): string {
  const source_label = edge_node_label(edge.source, node_map);
  const target_label = edge_node_label(edge.target, node_map);
  return `${source_label} -> ${edge.display_label ?? edge.label} -> ${target_label}`;
}

function summary_value(
  value: string | number | null | undefined,
  fallback = '—',
): string {
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return fallback;
}

function relation_preview_copy(relation: unknown, index: number) {
  const relation_record = to_record(relation);
  return {
    key: String(relation_record.id ?? `relation-${index}`),
    title: preview_text(relation_record, `关系 ${index + 1}`),
    description: preview_text(to_record(relation_record.metadata), '当前节点的一条关联关系。'),
  };
}

function read_text(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function read_number(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function paragraph_preview_copy(paragraph: unknown, index: number): PreviewCardRecord {
  const record = to_record(paragraph);
  const paragraph_id = read_text(record.id) ?? read_text(record.paragraph_id);
  const source_name =
    read_text(record.source_name) ??
    read_text(to_record(record.source).name) ??
    read_text(record.source_label);
  const position = read_number(record.position) ?? read_number(record.paragraph_position);
  const description_parts = [
    source_name ? `来源：${source_name}` : null,
    position !== null ? `段落 ${position + 1}` : null,
  ].filter(Boolean);

  return {
    key: paragraph_id ?? `paragraph-${index}`,
    title: preview_text(record, `段落 ${index + 1}`),
    description: description_parts.join(' · ') || '关联证据段落',
    paragraph_id,
    source_id: read_text(record.source_id),
  };
}

function source_preview_copy(source: unknown, index: number): PreviewCardRecord {
  const record = to_record(source);
  return {
    key: read_text(record.id) ?? `source-${index}`,
    title: preview_text(record, `来源 ${index + 1}`),
    description:
      read_text(record.summary) ??
      read_text(record.source_kind) ??
      read_text(record.file_type) ??
      '当前证据关联的来源',
    source_id: read_text(record.id) ?? read_text(record.source_id),
  };
}

function paragraph_focus_label(
  paragraph_id: string | null,
  node_detail: { paragraphs: Record<string, unknown>[] } | null,
  edge_detail: { paragraph: Record<string, unknown> | null } | null,
): string | null {
  if (!paragraph_id) {
    return null;
  }

  const candidates = [
    ...(node_detail?.paragraphs ?? []),
    ...(edge_detail?.paragraph ? [edge_detail.paragraph] : []),
  ];
  const matched = candidates.find((paragraph) => {
    const record = to_record(paragraph);
    return read_text(record.id) === paragraph_id || read_text(record.paragraph_id) === paragraph_id;
  });
  const record = matched ? to_record(matched) : {};
  const position = read_number(record.position) ?? read_number(record.paragraph_position);
  const source_name =
    read_text(record.source_name) ?? read_text(to_record(record.source).name) ?? null;

  if (position !== null && source_name) {
    return `定位段落：${source_name} · 第 ${position + 1} 段`;
  }
  if (position !== null) {
    return `定位段落：第 ${position + 1} 段`;
  }
  return `定位段落：${paragraph_id}`;
}

function array_without<T>(values: T[], value: T): T[] {
  return values.filter((item) => item !== value);
}

export function GraphBrowserPanel(props: GraphBrowserPanelProps) {
  const { resolved_theme } = props;
  const workspace = use_knowledge_base_workspace_context();
  const {
    graph,
    sources,
    manual_relations,
    selected_source_ids,
    include_paragraphs,
    density,
    selected_node_id,
    selected_edge_id,
    node_detail,
    edge_detail,
    graph_error_message,
    highlighted_node_ids,
    highlighted_edge_ids,
    is_graph_loading,
    is_creating_node,
    is_creating_manual_relation,
    is_renaming_node,
    is_deleting_node,
    is_deleting_edge,
    set_selected_source_ids,
    set_include_paragraphs,
    set_density,
    select_node,
    select_edge,
    clear_graph_selection,
    create_entity,
    create_relation,
    rename_node,
    delete_node,
    delete_edge,
    clear_highlights,
    refresh_graph,
    reset_graph_filters,
    clear_source_filters,
  } = use_graph_browser();

  const [layout_revision, set_layout_revision] = useState(0);
  const [graph_view_mode, set_graph_view_mode] = useState<GraphViewMode>('global');
  const [local_graph_state, set_local_graph_state] =
    useState<LocalGraphState>(DEFAULT_LOCAL_GRAPH_STATE);
  const [viewport_mode, set_viewport_mode] = useState<GraphViewportMode>('fit-all');
  const [viewport_command, set_viewport_command] = useState<ViewportCommand | null>(null);
  const [active_graph_drawer, set_active_graph_drawer] = useState<GraphDrawerMode>(null);
  const [active_layer_modes, set_active_layer_modes] =
    useState<GraphLayerMode[]>(DEFAULT_LAYER_MODES);
  const [source_keyword, set_source_keyword] = useState('');
  const [node_keyword, set_node_keyword] = useState('');
  const [is_search_open, set_is_search_open] = useState(false);
  const [active_search_index, set_active_search_index] = useState(0);
  const [rename_value, set_rename_value] = useState('');
  const [create_label, set_create_label] = useState('');
  const [create_description, set_create_description] = useState('');
  const [relation_draft, set_relation_draft] = useState<RelationDraft>(DEFAULT_RELATION_DRAFT);
  const search_shell_ref = useRef<HTMLDivElement | null>(null);

  const node_map = useMemo(
    () => new Map(graph.nodes.map((node) => [node.id, node])),
    [graph.nodes],
  );
  const selected_node = selected_node_id ? node_map.get(selected_node_id) ?? null : null;
  const selected_edge =
    selected_edge_id ? graph.edges.find((edge) => edge.id === selected_edge_id) ?? null : null;

  const source_scope_label = useMemo(
    () => selected_source_summary(selected_source_ids, sources),
    [selected_source_ids, sources],
  );

  const projected_graph = useMemo(
    () =>
      project_graph(graph, {
        active_layer_modes,
        include_paragraphs,
        selected_node_id,
        selected_edge_id,
        highlighted_node_ids,
        highlighted_edge_ids,
        graph_view_mode,
        local_graph_state,
      }),
    [
      active_layer_modes,
      graph,
      graph_view_mode,
      include_paragraphs,
      local_graph_state,
      selected_node_id,
      selected_edge_id,
      highlighted_node_ids,
      highlighted_edge_ids,
    ],
  );

  const relation_node_options = useMemo(
    () =>
      graph.nodes
        .filter((node) => node.type === 'entity')
        .sort((left, right) =>
          (left.display_label ?? left.label).localeCompare(
            right.display_label ?? right.label,
            'zh-CN',
          ),
        ),
    [graph.nodes],
  );

  const searchable_nodes = useMemo(
    () =>
      projected_graph.nodes
        .filter((node) => node.type === 'entity')
        .sort((left, right) =>
          (left.display_label ?? left.label).localeCompare(
            right.display_label ?? right.label,
            'zh-CN',
          ),
        ),
    [projected_graph.nodes],
  );

  const node_matches = useMemo<GraphSearchCandidateRecord[]>(() => {
    const keyword = normalize_keyword(node_keyword);
    const matches = !keyword
      ? searchable_nodes.slice(0, 8)
      : searchable_nodes.filter((node) => node_search_text(node).includes(keyword)).slice(0, 8);
    return matches.map(create_search_candidate);
  }, [node_keyword, searchable_nodes]);

  const filtered_sources = useMemo(() => {
    const keyword = normalize_keyword(source_keyword);
    return !keyword
      ? sources
      : sources.filter((source) =>
          `${source.name} ${source.summary ?? ''} ${source.source_kind}`
            .toLowerCase()
            .includes(keyword),
        );
  }, [source_keyword, sources]);

  const selected_node_copy = useMemo(
    () => (node_detail ? node_action_copy(node_detail) : null),
    [node_detail],
  );
  const selected_edge_copy = useMemo(
    () => (edge_detail ? edge_action_copy(edge_detail) : null),
    [edge_detail],
  );
  const selected_node_rows = useMemo(
    () => (node_detail ? collect_node_import_rows(node_detail.node.type, node_detail.node.metadata) : []),
    [node_detail],
  );
  const selected_edge_rows = useMemo(
    () => (edge_detail ? collect_edge_import_rows(edge_detail.edge.metadata) : []),
    [edge_detail],
  );
  const node_relation_previews = useMemo(
    () => (node_detail ? node_detail.relations.slice(0, 3).map(relation_preview_copy) : []),
    [node_detail],
  );
  const node_paragraph_previews = useMemo(
    () => (node_detail ? node_detail.paragraphs.slice(0, 3).map(paragraph_preview_copy) : []),
    [node_detail],
  );
  const node_source_previews = useMemo(() => {
    if (!node_detail) {
      return [];
    }
    const previews = new Map<string, PreviewCardRecord>();
    if (node_detail.source) {
      const source_preview = source_preview_copy(node_detail.source, 0);
      previews.set(source_preview.key, source_preview);
    }
    node_detail.paragraphs.forEach((paragraph, index) => {
      const record = to_record(paragraph);
      const source_id = read_text(record.source_id);
      const source_name =
        read_text(record.source_name) ??
        read_text(to_record(record.source).name) ??
        read_text(record.source_label);
      if (!source_id && !source_name) {
        return;
      }
      const preview = source_preview_copy(
        {
          id: source_id ?? `source-${index}`,
          name: source_name ?? `来源 ${index + 1}`,
          summary: typeof record.content === 'string' ? record.content : undefined,
        },
        index + 1,
      );
      previews.set(preview.key, preview);
    });
    return Array.from(previews.values()).slice(0, 3);
  }, [node_detail]);
  const edge_paragraph_preview = useMemo(
    () => (edge_detail?.paragraph ? paragraph_preview_copy(edge_detail.paragraph, 0) : null),
    [edge_detail],
  );
  const edge_source_preview = useMemo(() => {
    if (edge_detail?.source) {
      return source_preview_copy(edge_detail.source, 0);
    }
    if (edge_detail?.paragraph) {
      const record = to_record(edge_detail.paragraph);
      const source_id = read_text(record.source_id);
      const source_name =
        read_text(record.source_name) ?? read_text(to_record(record.source).name) ?? null;
      if (source_id || source_name) {
        return source_preview_copy(
          {
            id: source_id ?? 'edge-source',
            name: source_name ?? '来源',
          },
          0,
        );
      }
    }
    return null;
  }, [edge_detail]);
  const related_evidence_source_ids = useMemo(
    () =>
      Array.from(
        new Set(
          [...node_source_previews, ...(edge_source_preview ? [edge_source_preview] : [])]
            .map((preview) => preview.source_id)
            .filter((value): value is string => Boolean(value)),
        ),
      ),
    [edge_source_preview, node_source_previews],
  );

  const has_focus_target = Boolean(
    selected_node_id || selected_edge_id || highlighted_node_ids.length || highlighted_edge_ids.length,
  );
  const can_enter_local_graph = is_entity_node(selected_node);
  const evidence_layer_active = active_layer_modes.includes('evidence');
  const structure_layer_active = active_layer_modes.includes('structure');
  const left_drawer_mode = is_left_drawer(active_graph_drawer) ? active_graph_drawer : null;
  const inspector_open =
    active_graph_drawer === 'inspector' && Boolean(selected_node_id || selected_edge_id);
  const search_results_visible = is_search_open && Boolean(node_keyword.trim() || node_matches.length);
  const active_search_candidate = node_matches[active_search_index] ?? node_matches[0] ?? null;

  const current_focus_reason = useMemo(() => {
    if (selected_node) {
      return `当前焦点：${selected_node.display_label ?? selected_node.label}`;
    }
    if (selected_edge) {
      return `当前焦点：${relation_summary_text(selected_edge, node_map)}`;
    }
    if (highlighted_node_ids.length || highlighted_edge_ids.length) {
      return '当前焦点：高亮上下文';
    }
    return '当前焦点：全局图';
  }, [highlighted_edge_ids.length, highlighted_node_ids.length, node_map, selected_edge, selected_node]);
  const highlighted_source_id = useMemo(
    () =>
      highlighted_node_ids
        .find((node_id) => node_id.startsWith('source:'))
        ?.replace(/^source:/, '') ?? null,
    [highlighted_node_ids],
  );
  const highlighted_paragraph_id = useMemo(
    () =>
      highlighted_node_ids
        .find((node_id) => node_id.startsWith('paragraph:'))
        ?.replace(/^paragraph:/, '') ?? null,
    [highlighted_node_ids],
  );
  const current_highlight_reason_label = useMemo(() => {
    if (highlighted_paragraph_id || highlighted_source_id) {
      return '当前高亮原因：来源证据';
    }
    return current_focus_reason;
  }, [current_focus_reason, highlighted_paragraph_id, highlighted_source_id]);
  const current_paragraph_label = useMemo(
    () => paragraph_focus_label(highlighted_paragraph_id, node_detail, edge_detail),
    [edge_detail, highlighted_paragraph_id, node_detail],
  );

  const current_view_label = GRAPH_VIEW_MODE_LABELS[graph_view_mode];
  const selected_edge_source_label = selected_edge
    ? edge_node_label(selected_edge.source, node_map)
    : '';
  const selected_edge_target_label = selected_edge
    ? edge_node_label(selected_edge.target, node_map)
    : '';

  useEffect(() => {
    set_active_search_index((current) => {
      if (!node_matches.length) {
        return 0;
      }
      return Math.min(current, node_matches.length - 1);
    });
  }, [node_matches.length]);

  useEffect(() => {
    if (node_detail) {
      set_rename_value(node_detail.node.display_label ?? node_detail.node.label);
      set_active_graph_drawer('inspector');
    }
  }, [node_detail]);

  useEffect(() => {
    if (edge_detail) {
      set_active_graph_drawer('inspector');
    }
  }, [edge_detail]);

  useEffect(() => {
    if (!selected_node_id && !selected_edge_id && active_graph_drawer === 'inspector') {
      set_active_graph_drawer(null);
    }
  }, [active_graph_drawer, selected_edge_id, selected_node_id]);

  useEffect(() => {
    if (graph_view_mode !== 'local' || !is_entity_node(selected_node)) {
      return;
    }
    if (local_graph_state.anchor_node_id === selected_node.id) {
      return;
    }
    set_local_graph_state({
      anchor_node_id: selected_node.id,
      depth: 1,
    });
  }, [graph_view_mode, local_graph_state.anchor_node_id, selected_node]);

  function open_left_drawer(mode: 'filters' | 'create-node' | 'relation'): void {
    set_active_graph_drawer(mode);
  }

  function close_left_drawer(): void {
    if (left_drawer_mode) {
      set_active_graph_drawer(null);
    }
  }

  function close_inspector(): void {
    if (active_graph_drawer === 'inspector') {
      set_active_graph_drawer(null);
    }
  }

  function run_viewport(type: ViewportCommand['type']): void {
    if (type === 'fit-all' || type === 'focus-selection') {
      set_viewport_mode(type);
    }
    set_viewport_command(create_viewport_command(type));
  }

  function fit_all(): void {
    run_viewport('fit-all');
  }

  function focus_selected(): void {
    if (!has_focus_target) {
      return;
    }
    run_viewport('focus-selection');
  }

  function enter_global_graph(): void {
    set_graph_view_mode('global');
    set_local_graph_state(DEFAULT_LOCAL_GRAPH_STATE);
    fit_all();
  }

  function enter_local_graph(): void {
    if (!is_entity_node(selected_node)) {
      return;
    }
    set_graph_view_mode('local');
    set_local_graph_state({
      anchor_node_id: selected_node.id,
      depth: 1,
    });
    focus_selected();
  }

  function handle_select_node(node_id: string): void {
    select_node(node_id);
    set_active_graph_drawer('inspector');
    if (graph_view_mode === 'local') {
      set_local_graph_state({
        anchor_node_id: node_id,
        depth: 1,
      });
    }
    focus_selected();
  }

  function handle_select_edge(edge_id: string): void {
    select_edge(edge_id);
    set_active_graph_drawer('inspector');
    focus_selected();
  }

  function handle_clear_selection(): void {
    clear_graph_selection();
    if (active_graph_drawer === 'inspector') {
      close_inspector();
    }
  }

  function handle_clear_all(): void {
    set_node_keyword('');
    set_is_search_open(false);
    set_active_search_index(0);
    clear_graph_selection();
    clear_highlights();
    set_local_graph_state(DEFAULT_LOCAL_GRAPH_STATE);
    set_graph_view_mode('global');
    set_active_graph_drawer(null);
    fit_all();
  }

  async function handle_refresh_graph(): Promise<void> {
    await refresh_graph();
    if (graph_view_mode === 'local' && has_focus_target) {
      focus_selected();
      return;
    }
    fit_all();
  }

  function choose_search_candidate(candidate: GraphSearchCandidateRecord): void {
    set_node_keyword(candidate.label);
    set_is_search_open(false);
    set_active_search_index(0);
    handle_select_node(candidate.id);
  }

  function handle_apply_search(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!active_search_candidate) {
      return;
    }
    choose_search_candidate(active_search_candidate);
  }

  function handle_search_key_down(event: KeyboardEvent<HTMLInputElement>): void {
    if (!search_results_visible && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      set_is_search_open(true);
      return;
    }
    if (!node_matches.length) {
      if (event.key === 'Escape') {
        set_is_search_open(false);
      }
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      set_active_search_index((current) => (current + 1) % node_matches.length);
      set_is_search_open(true);
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      set_active_search_index((current) => (current - 1 + node_matches.length) % node_matches.length);
      set_is_search_open(true);
      return;
    }
    if (event.key === 'Enter') {
      if (is_search_open && active_search_candidate) {
        event.preventDefault();
        choose_search_candidate(active_search_candidate);
      }
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      set_is_search_open(false);
    }
  }

  function handle_search_shell_blur(event: FocusEvent<HTMLDivElement>): void {
    const next_target = event.relatedTarget as Node | null;
    if (next_target && search_shell_ref.current?.contains(next_target)) {
      return;
    }
    set_is_search_open(false);
  }

  function handle_toggle_source(source_id: string): void {
    set_selected_source_ids((current) =>
      current.includes(source_id)
        ? current.filter((item) => item !== source_id)
        : [...current, source_id],
    );
  }

  function toggle_layer_mode(layer_mode: GraphLayerMode): void {
    set_active_layer_modes((current) => {
      const next = current.includes(layer_mode)
        ? array_without(current, layer_mode)
        : [...current, layer_mode];
      if (!next.length) {
        return ['semantic'];
      }
      if (!next.includes('semantic')) {
        return ['semantic', ...next];
      }
      return next;
    });
  }

  function open_evidence_entry(): void {
    set_active_layer_modes((current) =>
      current.includes('evidence') ? current : [...current, 'evidence'],
    );
    if (related_evidence_source_ids.length) {
      set_selected_source_ids(related_evidence_source_ids);
    }
    if ((node_detail?.paragraphs.length ?? 0) > 0 || edge_detail?.paragraph) {
      set_include_paragraphs(true);
    }
    if (has_focus_target) {
      focus_selected();
    }
  }

  function focus_evidence_paragraph(paragraph_id: string): void {
    workspace.focus_paragraph(paragraph_id);
  }

  function open_evidence_source(source_id: string): void {
    workspace.focus_source(source_id);
  }

  function highlight_current_evidence(source_id?: string | null, paragraph_id?: string | null): void {
    if (source_id && paragraph_id) {
      workspace.focus_citation(source_id, paragraph_id);
      return;
    }
    if (paragraph_id) {
      workspace.focus_paragraph(paragraph_id);
      return;
    }
    if (source_id) {
      set_active_layer_modes((current) =>
        current.includes('evidence') ? current : [...current, 'evidence'],
      );
      set_selected_source_ids([source_id]);
      select_node(`source:${source_id}`);
      set_active_graph_drawer('inspector');
      focus_selected();
      return;
    }
    open_evidence_entry();
  }

  async function handle_create_entity(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const label = create_label.trim();
    if (!label) {
      return;
    }
    const description = create_description.trim();
    const scoped_source_id = selected_source_ids.length === 1 ? selected_source_ids[0] : null;
    await create_entity(label, {
      description: description || undefined,
      source_id: scoped_source_id,
      metadata: {
        ...(description ? { description } : {}),
        ...(scoped_source_id ? { source_id: scoped_source_id } : {}),
      },
    });
    set_create_label('');
    set_create_description('');
  }

  async function handle_create_relation(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const { subject_node_id, predicate, object_node_id, weight } = relation_draft;
    if (!subject_node_id || !object_node_id || !predicate.trim() || subject_node_id === object_node_id) {
      return;
    }
    await create_relation(subject_node_id, predicate.trim(), object_node_id, weight);
    set_relation_draft((current) => ({
      ...current,
      predicate: current.predicate.trim() || DEFAULT_PREDICATE,
      object_node_id: '',
    }));
  }

  async function handle_rename_node(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!node_detail) {
      return;
    }
    const next_label = rename_value.trim();
    const current_label = node_detail.node.display_label ?? node_detail.node.label;
    if (!next_label || next_label === current_label) {
      return;
    }
    await rename_node(node_detail.node.id, next_label);
  }

  async function handle_delete_selected_node(): Promise<void> {
    if (!node_detail || !selected_node_copy?.delete_allowed) {
      return;
    }
    if (!window.confirm(selected_node_copy.delete_message)) {
      return;
    }
    await delete_node(node_detail.node.id);
    close_inspector();
    if (graph_view_mode === 'local') {
      enter_global_graph();
      return;
    }
    fit_all();
  }

  async function handle_delete_selected_edge(): Promise<void> {
    if (!edge_detail || !selected_edge_copy?.delete_allowed) {
      return;
    }
    if (!window.confirm(selected_edge_copy.delete_message)) {
      return;
    }
    await delete_edge(edge_detail.edge.id);
    close_inspector();
    fit_all();
  }

  function assign_relation_endpoint(role: 'subject' | 'object', node_id?: string): void {
    const next_node_id = node_id ?? selected_node_id ?? '';
    const node = next_node_id ? node_map.get(next_node_id) ?? null : null;
    if (!is_entity_node(node)) {
      return;
    }
    open_left_drawer('relation');
    set_relation_draft((current) => ({
      ...current,
      subject_node_id: role === 'subject' ? next_node_id : current.subject_node_id,
      object_node_id: role === 'object' ? next_node_id : current.object_node_id,
    }));
  }

  function start_relation_from_current_node(): void {
    if (!is_entity_node(selected_node)) {
      return;
    }
    open_left_drawer('relation');
    set_relation_draft((current) => ({
      ...current,
      subject_node_id: current.subject_node_id || selected_node.id,
    }));
  }

  function copy_edge_to_relation_form(): void {
    if (!edge_detail) {
      return;
    }
    const subject_node = node_map.get(edge_detail.edge.source) ?? null;
    const object_node = node_map.get(edge_detail.edge.target) ?? null;
    if (!is_entity_node(subject_node) || !is_entity_node(object_node)) {
      return;
    }
    open_left_drawer('relation');
    set_relation_draft({
      subject_node_id: edge_detail.edge.source,
      predicate: edge_detail.edge.display_label || edge_detail.edge.label || DEFAULT_PREDICATE,
      object_node_id: edge_detail.edge.target,
      weight: edge_detail.edge.weight || 0.9,
    });
  }

  function relayout_graph(): void {
    set_layout_revision((current) => current + 1);
    run_viewport('relayout');
  }

  function render_left_drawer() {
    if (!left_drawer_mode) {
      return null;
    }

    if (left_drawer_mode === 'filters') {
      return (
        <>
          <div className='kb-graph-drawer-head'>
            <div>
              <span className='kb-context-label'>筛选与显示</span>
              <h3>主图范围</h3>
              <p>{source_scope_label}</p>
            </div>
            <button className='kb-secondary-button' onClick={close_left_drawer} type='button'>
              关闭
            </button>
          </div>

          <label className='kb-form-field'>
            <span>来源搜索</span>
            <input
              onChange={(event) => set_source_keyword(event.target.value)}
              placeholder='按名称、摘要或类型搜索来源'
              value={source_keyword}
            />
          </label>

          <div className='kb-graph-source-list'>
            {filtered_sources.map((source) => (
              <label className='kb-graph-source-option' key={source.id}>
                <input
                  checked={selected_source_ids.includes(source.id)}
                  onChange={() => handle_toggle_source(source.id)}
                  type='checkbox'
                />
                <div>
                  <strong>{format_source_display_name(source, sources)}</strong>
                  <span>{source.summary || source.source_kind}</span>
                </div>
              </label>
            ))}
            {!filtered_sources.length ? <div className='kb-helper-text'>没有匹配的来源。</div> : null}
          </div>

          <section className='kb-graph-form'>
            <strong>高级显示选项</strong>

            <label className='kb-check-field'>
              <input
                checked={evidence_layer_active}
                onChange={() => toggle_layer_mode('evidence')}
                type='checkbox'
              />
              <span>{GRAPH_LAYER_LABELS.evidence}</span>
            </label>

            <label className='kb-check-field'>
              <input
                checked={structure_layer_active}
                onChange={() => toggle_layer_mode('structure')}
                type='checkbox'
              />
              <span>{GRAPH_LAYER_LABELS.structure}</span>
            </label>

            <label className='kb-check-field'>
              <input
                checked={include_paragraphs}
                disabled={!evidence_layer_active}
                onChange={(event) => set_include_paragraphs(event.target.checked)}
                type='checkbox'
              />
              <span>显示段落节点</span>
            </label>
          </section>

          <label className='kb-form-field'>
            <span>{`图谱密度 ${density}%`}</span>
            <input
              max={100}
              min={12}
              onChange={(event) => set_density(Number(event.target.value))}
              type='range'
              value={density}
            />
          </label>

          <div className='kb-button-row'>
            {DENSITY_PRESETS.map((value) => (
              <button className='kb-chip' key={value} onClick={() => set_density(value)} type='button'>
                {`${value}%`}
              </button>
            ))}
          </div>

          <div className='kb-button-row'>
            <button className='kb-secondary-button' onClick={clear_source_filters} type='button'>
              清空来源
            </button>
            <button className='kb-secondary-button' onClick={reset_graph_filters} type='button'>
              重置筛选
            </button>
          </div>
        </>
      );
    }

    if (left_drawer_mode === 'create-node') {
      return (
        <form className='kb-graph-form' onSubmit={(event) => void handle_create_entity(event)}>
          <div className='kb-graph-drawer-head'>
            <div>
              <span className='kb-context-label'>新建实体</span>
              <h3>新建手工实体</h3>
              <p>创建后会自动选中该实体，并可继续在右侧属性面板里编辑。</p>
            </div>
            <button className='kb-secondary-button' onClick={close_left_drawer} type='button'>
              关闭
            </button>
          </div>

          <label className='kb-form-field'>
            <span>实体名称</span>
            <input
              onChange={(event) => set_create_label(event.target.value)}
              placeholder='例如：项目 Alpha'
              value={create_label}
            />
          </label>

          <label className='kb-form-field'>
            <span>描述</span>
            <textarea
              onChange={(event) => set_create_description(event.target.value)}
              placeholder='补充实体说明，创建后会写入节点元数据。'
              value={create_description}
            />
          </label>

          <div className='kb-button-row'>
            <button
              className='kb-primary-button'
              disabled={is_creating_node || !create_label.trim()}
              type='submit'
            >
              {is_creating_node ? '创建中…' : '创建实体'}
            </button>
          </div>
        </form>
      );
    }

    return (
      <form className='kb-graph-form' onSubmit={(event) => void handle_create_relation(event)}>
        <div className='kb-graph-drawer-head'>
          <div>
            <span className='kb-context-label'>补关系</span>
            <h3>实体到实体</h3>
            <p>手动补边仅允许实体与实体之间建立关系。</p>
          </div>
          <button className='kb-secondary-button' onClick={close_left_drawer} type='button'>
            关闭
          </button>
        </div>

        {is_entity_node(selected_node) ? (
          <div className='kb-button-row'>
            <button
              className='kb-chip'
              onClick={() => assign_relation_endpoint('subject', selected_node.id)}
              type='button'
            >
              用当前节点作为起点
            </button>
            <button
              className='kb-chip'
              onClick={() => assign_relation_endpoint('object', selected_node.id)}
              type='button'
            >
              用当前节点作为终点
            </button>
          </div>
        ) : null}

        <label className='kb-form-field'>
          <span>起点实体</span>
          <select
            onChange={(event) =>
              set_relation_draft((current) => ({ ...current, subject_node_id: event.target.value }))
            }
            value={relation_draft.subject_node_id}
          >
            <option value=''>请选择起点实体</option>
            {relation_node_options.map((node) => (
              <option key={node.id} value={node.id}>
                {node_option_label(node.id, graph)}
              </option>
            ))}
          </select>
        </label>

        <label className='kb-form-field'>
          <span>关系谓词</span>
          <input
            list='kb-graph-predicate-options'
            onChange={(event) =>
              set_relation_draft((current) => ({ ...current, predicate: event.target.value }))
            }
            placeholder='例如：依赖 / 属于 / 引用'
            value={relation_draft.predicate}
          />
          <datalist id='kb-graph-predicate-options'>
            {PREDICATE_SUGGESTIONS.map((predicate) => (
              <option key={predicate} value={predicate} />
            ))}
          </datalist>
        </label>

        <label className='kb-form-field'>
          <span>终点实体</span>
          <select
            onChange={(event) =>
              set_relation_draft((current) => ({ ...current, object_node_id: event.target.value }))
            }
            value={relation_draft.object_node_id}
          >
            <option value=''>请选择终点实体</option>
            {relation_node_options.map((node) => (
              <option key={node.id} value={node.id}>
                {node_option_label(node.id, graph)}
              </option>
            ))}
          </select>
        </label>

        <label className='kb-form-field'>
          <span>{`关系权重 ${relation_draft.weight.toFixed(2)}`}</span>
          <input
            max={1}
            min={0.1}
            onChange={(event) =>
              set_relation_draft((current) => ({ ...current, weight: Number(event.target.value) }))
            }
            step={0.05}
            type='range'
            value={relation_draft.weight}
          />
        </label>

        <div className='kb-helper-text'>{`当前共有 ${manual_relations.length} 条手工关系。`}</div>

        <div className='kb-button-row'>
          <button
            className='kb-primary-button'
            disabled={
              is_creating_manual_relation ||
              !relation_draft.subject_node_id ||
              !relation_draft.object_node_id ||
              !relation_draft.predicate.trim() ||
              relation_draft.subject_node_id === relation_draft.object_node_id
            }
            type='submit'
          >
            {is_creating_manual_relation ? '提交中…' : '创建关系'}
          </button>
        </div>
      </form>
    );
  }

  function render_inspector() {
    if (!inspector_open) {
      return null;
    }

    if (!node_detail && !edge_detail) {
      return (
        <div className='kb-graph-drawer-loading'>
          <span className='kb-context-label'>属性面板</span>
          <strong>正在加载详情…</strong>
          <span className='kb-helper-text'>详情会根据当前选中的节点或边自动更新。</span>
        </div>
      );
    }

    if (node_detail) {
      const node_source_name =
        typeof to_record(node_detail.source).name === 'string'
          ? (to_record(node_detail.source).name as string)
          : '';
      const node_source = summary_value(
        selected_node?.source_name ?? summary_value(node_source_name, ''),
        '未关联来源',
      );

      return (
        <div className='kb-graph-inspector-content'>
          <div className='kb-graph-drawer-head'>
            <div>
              <span className='kb-context-label'>属性面板</span>
              <h3>{node_detail.node.display_label ?? node_detail.node.label}</h3>
              <p>{node_kind_label(node_detail.node)}</p>
            </div>
            <button className='kb-secondary-button' onClick={close_inspector} type='button'>
              关闭
            </button>
          </div>

          <div className='kb-graph-summary-grid'>
            <section className='kb-graph-summary-card'>
              <strong>属性</strong>
              <div className='kb-graph-summary-list'>
                <div className='kb-graph-summary-item'>
                  <span>类型</span>
                  <strong>{node_kind_label(node_detail.node)}</strong>
                </div>
                <div className='kb-graph-summary-item'>
                  <span>来源</span>
                  <strong>{node_source}</strong>
                </div>
                <div className='kb-graph-summary-item'>
                  <span>段落数</span>
                  <strong>{node_detail.paragraphs.length}</strong>
                </div>
                <div className='kb-graph-summary-item'>
                  <span>关系数</span>
                  <strong>{node_detail.relations.length}</strong>
                </div>
              </div>
            </section>

            <section className='kb-graph-summary-card'>
              <strong>关系摘要</strong>
              <div className='kb-graph-summary-preview-list'>
                {node_relation_previews.length ? (
                  node_relation_previews.map((relation) => (
                    <div className='kb-graph-summary-preview' key={relation.key}>
                      <strong>{relation.title}</strong>
                      <span>{relation.description}</span>
                    </div>
                  ))
                ) : (
                  <div className='kb-graph-summary-item'>
                    <span>当前节点暂无可预览关系。</span>
                  </div>
                )}
              </div>
            </section>

            <section className='kb-graph-summary-card'>
              <strong>证据入口</strong>
              <div className='kb-graph-summary-list'>
                <div className='kb-graph-summary-item'>
                  <span>高亮原因</span>
                  <strong>{current_highlight_reason_label}</strong>
                </div>
                <div className='kb-graph-summary-item'>
                  <span>证据层</span>
                  <strong>{evidence_layer_active ? '已开启' : '未开启'}</strong>
                </div>
                {current_paragraph_label ? (
                  <div className='kb-graph-summary-item'>
                    <span>定位段落</span>
                    <strong>{current_paragraph_label.replace('定位段落：', '')}</strong>
                  </div>
                ) : null}
              </div>
              <div className='kb-button-row'>
                <button className='kb-secondary-button' onClick={open_evidence_entry} type='button'>
                  展开证据层
                </button>
                {(node_detail.paragraphs.length > 0 || include_paragraphs) && evidence_layer_active ? (
                  <button
                    className='kb-secondary-button'
                    onClick={() => set_include_paragraphs(true)}
                    type='button'
                  >
                    显示段落节点
                  </button>
                ) : null}
              </div>
            </section>
          </div>

          {selected_node_copy?.rename_allowed ? (
            <form className='kb-graph-inline-form' onSubmit={(event) => void handle_rename_node(event)}>
              <input onChange={(event) => set_rename_value(event.target.value)} value={rename_value} />
              <button
                className='kb-secondary-button'
                disabled={is_renaming_node || !rename_value.trim()}
                type='submit'
              >
                {is_renaming_node ? '保存中…' : '重命名'}
              </button>
            </form>
          ) : null}

          <div className='kb-button-row'>
            {selected_node_copy?.relation_allowed ? (
              <>
                <button className='kb-secondary-button' onClick={() => assign_relation_endpoint('subject')} type='button'>
                  设为起点
                </button>
                <button className='kb-secondary-button' onClick={() => assign_relation_endpoint('object')} type='button'>
                  设为终点
                </button>
                <button className='kb-secondary-button' onClick={start_relation_from_current_node} type='button'>
                  从当前节点补关系
                </button>
              </>
            ) : null}

            <button className='kb-secondary-button' onClick={focus_selected} type='button'>
              聚焦节点
            </button>
            <button className='kb-secondary-button' onClick={clear_highlights} type='button'>
              清空高亮
            </button>
            <button className='kb-secondary-button' onClick={handle_clear_selection} type='button'>
              清空选择
            </button>
            {selected_node_copy?.delete_allowed ? (
              <button
                className='kb-secondary-button is-danger'
                disabled={is_deleting_node}
                onClick={() => void handle_delete_selected_node()}
                type='button'
              >
                {is_deleting_node ? '删除中…' : selected_node_copy.delete_label}
              </button>
            ) : null}
          </div>

          <MetadataRows rows={selected_node_rows} />

          <section className='kb-graph-summary-card'>
            <strong>关联段落</strong>
            <div className='kb-graph-summary-preview-list'>
              {node_paragraph_previews.length ? (
                node_paragraph_previews.map((paragraph) => (
                  <div className='kb-graph-summary-preview' key={paragraph.key}>
                    <strong>{paragraph.title}</strong>
                    <span>{paragraph.description}</span>
                    <div className='kb-button-row'>
                      {paragraph.paragraph_id ? (
                        <button
                          className='kb-secondary-button'
                          onClick={() => focus_evidence_paragraph(paragraph.paragraph_id!)}
                          type='button'
                        >
                          定位段落
                        </button>
                      ) : null}
                      {paragraph.source_id ? (
                        <button
                          className='kb-secondary-button'
                          onClick={() => open_evidence_source(paragraph.source_id!)}
                          type='button'
                        >
                          在来源中查看
                        </button>
                      ) : null}
                      {(paragraph.paragraph_id || paragraph.source_id) ? (
                        <button
                          className='kb-secondary-button'
                          onClick={() =>
                            highlight_current_evidence(paragraph.source_id, paragraph.paragraph_id)
                          }
                          type='button'
                        >
                          在图谱中高亮当前证据
                        </button>
                      ) : null}
                    </div>
                  </div>
                ))
              ) : (
                <div className='kb-graph-summary-item'>
                  <span>当前节点暂无可展开的证据段落。</span>
                </div>
              )}
            </div>
          </section>

          <section className='kb-graph-summary-card'>
            <strong>关联来源</strong>
            <div className='kb-graph-summary-preview-list'>
              {node_source_previews.length ? (
                node_source_previews.map((source_preview) => (
                  <div className='kb-graph-summary-preview' key={source_preview.key}>
                    <strong>{source_preview.title}</strong>
                    <span>{source_preview.description}</span>
                    <div className='kb-button-row'>
                      {source_preview.source_id ? (
                        <>
                          <button
                            className='kb-secondary-button'
                            onClick={() => open_evidence_source(source_preview.source_id!)}
                            type='button'
                          >
                            在来源中查看
                          </button>
                          <button
                            className='kb-secondary-button'
                            onClick={() => highlight_current_evidence(source_preview.source_id, null)}
                            type='button'
                          >
                            在图谱中高亮当前证据
                          </button>
                        </>
                      ) : null}
                    </div>
                  </div>
                ))
              ) : (
                <div className='kb-graph-summary-item'>
                  <span>当前节点暂无可展开的关联来源。</span>
                </div>
              )}
            </div>
          </section>

          <section className='kb-graph-summary-card'>
            <strong>关联关系</strong>
            <div className='kb-graph-summary-preview-list'>
              {node_relation_previews.length ? (
                node_relation_previews.map((relation) => (
                  <div className='kb-graph-summary-preview' key={relation.key}>
                    <strong>{relation.title}</strong>
                    <span>{relation.description}</span>
                  </div>
                ))
              ) : (
                <div className='kb-graph-summary-item'>
                  <span>当前节点暂无更多关联关系。</span>
                </div>
              )}
            </div>
          </section>

          <JsonDetails title='节点元数据' value={node_detail.node.metadata} />
          {node_detail.source ? <JsonDetails title='来源信息' value={to_record(node_detail.source)} /> : null}
          {node_detail.paragraphs.length ? (
            <JsonDetails title='关联段落详情' value={{ paragraphs: node_detail.paragraphs }} />
          ) : null}
          {node_detail.relations.length ? (
            <JsonDetails title='关联关系详情' value={{ relations: node_detail.relations }} />
          ) : null}
        </div>
      );
    }

    if (!edge_detail || !selected_edge) {
      return null;
    }

    return (
      <div className='kb-graph-inspector-content'>
        <div className='kb-graph-drawer-head'>
          <div>
            <span className='kb-context-label'>属性面板</span>
            <h3>{edge_detail.edge.display_label ?? edge_detail.edge.label}</h3>
            <p>{summary_value(edge_detail.edge.relation_kind_label, edge_detail.edge.type)}</p>
          </div>
          <button className='kb-secondary-button' onClick={close_inspector} type='button'>
            关闭
          </button>
        </div>

        <div className='kb-graph-summary-grid is-edge'>
          <section className='kb-graph-summary-card'>
            <strong>属性</strong>
            <div className='kb-graph-summary-list'>
              <div className='kb-graph-summary-item'>
                <span>关系类型</span>
                <strong>{summary_value(edge_detail.edge.relation_kind_label, edge_detail.edge.type)}</strong>
              </div>
              <div className='kb-graph-summary-item'>
                <span>起点</span>
                <strong>{selected_edge_source_label}</strong>
              </div>
              <div className='kb-graph-summary-item'>
                <span>终点</span>
                <strong>{selected_edge_target_label}</strong>
              </div>
              <div className='kb-graph-summary-item'>
                <span>权重</span>
                <strong>{summary_value(edge_detail.edge.weight)}</strong>
              </div>
            </div>
          </section>

          <section className='kb-graph-summary-card'>
            <strong>操作</strong>
            <div className='kb-button-row'>
              <button className='kb-secondary-button' onClick={focus_selected} type='button'>
                聚焦两端节点
              </button>
              {selected_edge_copy?.copy_allowed ? (
                <button className='kb-secondary-button' onClick={copy_edge_to_relation_form} type='button'>
                  复制到补关系表单
                </button>
              ) : null}
              {selected_edge_copy?.delete_allowed ? (
                <button
                  className='kb-secondary-button is-danger'
                  disabled={is_deleting_edge}
                  onClick={() => void handle_delete_selected_edge()}
                  type='button'
                >
                  {is_deleting_edge ? '删除中…' : '删除关系'}
                </button>
              ) : null}
            </div>
          </section>

          <section className='kb-graph-summary-card'>
            <strong>证据入口</strong>
            <div className='kb-graph-summary-list'>
              <div className='kb-graph-summary-item'>
                <span>高亮原因</span>
                <strong>{current_highlight_reason_label}</strong>
              </div>
              <div className='kb-graph-summary-item'>
                <span>证据层</span>
                <strong>{evidence_layer_active ? '已开启' : '未开启'}</strong>
              </div>
              {current_paragraph_label ? (
                <div className='kb-graph-summary-item'>
                  <span>定位段落</span>
                  <strong>{current_paragraph_label.replace('定位段落：', '')}</strong>
                </div>
              ) : null}
            </div>
            <div className='kb-button-row'>
              <button className='kb-secondary-button' onClick={open_evidence_entry} type='button'>
                展开证据层
              </button>
            </div>
          </section>
        </div>

        <MetadataRows rows={selected_edge_rows} />

        {edge_paragraph_preview ? (
          <section className='kb-graph-summary-card'>
            <strong>证据段落</strong>
            <div className='kb-graph-summary-preview-list'>
              <div className='kb-graph-summary-preview' key={edge_paragraph_preview.key}>
                <strong>{edge_paragraph_preview.title}</strong>
                <span>{edge_paragraph_preview.description}</span>
                <div className='kb-button-row'>
                  {edge_paragraph_preview.paragraph_id ? (
                    <button
                      className='kb-secondary-button'
                      onClick={() => focus_evidence_paragraph(edge_paragraph_preview.paragraph_id!)}
                      type='button'
                    >
                      定位段落
                    </button>
                  ) : null}
                  {edge_paragraph_preview.source_id ? (
                    <button
                      className='kb-secondary-button'
                      onClick={() => open_evidence_source(edge_paragraph_preview.source_id!)}
                      type='button'
                    >
                      在来源中查看
                    </button>
                  ) : null}
                  {(edge_paragraph_preview.paragraph_id || edge_paragraph_preview.source_id) ? (
                    <button
                      className='kb-secondary-button'
                      onClick={() =>
                        highlight_current_evidence(
                          edge_paragraph_preview.source_id,
                          edge_paragraph_preview.paragraph_id,
                        )
                      }
                      type='button'
                    >
                      在图谱中高亮当前证据
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          </section>
        ) : null}

        {edge_source_preview ? (
          <section className='kb-graph-summary-card'>
            <strong>证据来源</strong>
            <div className='kb-graph-summary-preview-list'>
              <div className='kb-graph-summary-preview' key={edge_source_preview.key}>
                <strong>{edge_source_preview.title}</strong>
                <span>{edge_source_preview.description}</span>
                <div className='kb-button-row'>
                  {edge_source_preview.source_id ? (
                    <>
                      <button
                        className='kb-secondary-button'
                        onClick={() => open_evidence_source(edge_source_preview.source_id!)}
                        type='button'
                      >
                        在来源中查看
                      </button>
                      <button
                        className='kb-secondary-button'
                        onClick={() => highlight_current_evidence(edge_source_preview.source_id, null)}
                        type='button'
                      >
                        在图谱中高亮当前证据
                      </button>
                    </>
                  ) : null}
                </div>
              </div>
            </div>
          </section>
        ) : null}

        <section className='kb-graph-summary-card'>
          <strong>关系来源说明</strong>
          <div className='kb-graph-summary-preview-list'>
            <div className='kb-graph-summary-preview'>
              <strong>{summary_value(edge_detail.edge.display_label, edge_detail.edge.label)}</strong>
              <span>
                {[
                  summary_value(edge_detail.edge.relation_kind_label, edge_detail.edge.type),
                  edge_detail.edge.source_name ? `来源：${edge_detail.edge.source_name}` : null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </div>
          </div>
        </section>

        <JsonDetails title='关系元数据' value={edge_detail.edge.metadata} />
        {edge_detail.source ? <JsonDetails title='来源信息' value={to_record(edge_detail.source)} /> : null}
        {edge_detail.paragraph ? (
          <JsonDetails title='段落信息' value={to_record(edge_detail.paragraph)} />
        ) : null}
      </div>
    );
  }

  return (
    <section className='kb-panel kb-graph-page'>
      <section className='kb-graph-toolbar'>
        <div className='kb-graph-toolbar-row'>
          <div className='kb-graph-toolbar-copy'>
            <span className='kb-context-label'>知识图谱</span>
            <strong>语义主图</strong>
            <span className='kb-helper-text'>
              默认先阅读实体关系；证据和结构从抽屉与属性面板中下钻。
            </span>
          </div>

          <div className='kb-button-row'>
            <button className='kb-secondary-button' onClick={() => open_left_drawer('filters')} type='button'>
              筛选与显示
            </button>
            <button className='kb-secondary-button' onClick={() => open_left_drawer('create-node')} type='button'>
              新建实体
            </button>
            <button className='kb-secondary-button' onClick={() => open_left_drawer('relation')} type='button'>
              补关系
            </button>
          </div>
        </div>

        <div className='kb-graph-toolbar-row is-controls'>
          <form className='kb-graph-search-form' onSubmit={handle_apply_search}>
            <div
              className='kb-graph-search-shell'
              onBlur={handle_search_shell_blur}
              ref={search_shell_ref}
            >
              <label className='kb-form-field'>
                <span>快速定位</span>
                <input
                  onChange={(event) => {
                    set_node_keyword(event.target.value);
                    set_active_search_index(0);
                    set_is_search_open(true);
                  }}
                  onFocus={() => set_is_search_open(true)}
                  onKeyDown={handle_search_key_down}
                  placeholder='搜索实体名称、类型或来源'
                  value={node_keyword}
                />
              </label>

              {search_results_visible ? (
                <div className='kb-graph-search-results'>
                  {node_matches.length ? (
                    node_matches.map((candidate, index) => (
                      <button
                        className={`kb-graph-search-result ${index === active_search_index ? 'is-active' : ''}`}
                        key={candidate.id}
                        onClick={() => choose_search_candidate(candidate)}
                        tabIndex={0}
                        type='button'
                      >
                        <div className='kb-graph-search-result-head'>
                          <strong>{candidate.label}</strong>
                          <span>{candidate.kind_label}</span>
                        </div>
                        <span>{candidate.description}</span>
                      </button>
                    ))
                  ) : (
                    <div className='kb-graph-search-result'>
                      <strong>没有匹配的语义节点</strong>
                      <span>尝试更换关键词，或调整筛选范围。</span>
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            <button
              className='kb-secondary-button'
              disabled={!active_search_candidate}
              type='submit'
            >
              定位
            </button>
          </form>

          <div className='kb-graph-toolbar-actions'>
            <button
              aria-pressed={graph_view_mode === 'global'}
              className='kb-secondary-button'
              onClick={enter_global_graph}
              type='button'
            >
              全局图
            </button>
            <button
              aria-pressed={graph_view_mode === 'local'}
              className='kb-secondary-button'
              disabled={!can_enter_local_graph}
              onClick={enter_local_graph}
              type='button'
            >
              局部图
            </button>
            <button className='kb-secondary-button' onClick={() => void handle_refresh_graph()} type='button'>
              刷新图谱
            </button>
            <button className='kb-secondary-button' onClick={fit_all} type='button'>
              适配全图
            </button>
            <button
              className='kb-secondary-button'
              disabled={!has_focus_target}
              onClick={focus_selected}
              type='button'
            >
              聚焦选中
            </button>
            <button className='kb-secondary-button' onClick={() => run_viewport('zoom-in')} type='button'>
              放大
            </button>
            <button className='kb-secondary-button' onClick={() => run_viewport('zoom-out')} type='button'>
              缩小
            </button>
            <button className='kb-secondary-button' onClick={relayout_graph} type='button'>
              重新布局
            </button>
            <button className='kb-secondary-button' onClick={handle_clear_all} type='button'>
              一键清空
            </button>
          </div>
        </div>
      </section>

      {graph_error_message ? <div className='kb-graph-error-banner'>{graph_error_message}</div> : null}

      <section className='kb-graph-stage'>
        <PixiKnowledgeGraphCanvas
          edges={projected_graph.edges}
          graph_view_mode={graph_view_mode}
          highlighted_edge_ids={highlighted_edge_ids}
          highlighted_node_ids={highlighted_node_ids}
          layout_revision={layout_revision}
          nodes={projected_graph.nodes}
          on_clear_selection={handle_clear_selection}
          on_select_edge={handle_select_edge}
          on_select_node={handle_select_node}
          resolved_theme={resolved_theme}
          selected_edge_id={selected_edge_id}
          selected_node_id={selected_node_id}
          viewport_command={viewport_command}
          viewport_mode={viewport_mode}
        />

        <div className='kb-graph-stage-badges'>
          <span className='kb-meta-pill'>{source_scope_label}</span>
          <span className='kb-meta-pill'>{current_highlight_reason_label}</span>
          {current_paragraph_label ? <span className='kb-meta-pill'>{current_paragraph_label}</span> : null}
          <span className='kb-meta-pill'>{`投影节点 ${projected_graph.nodes.length}`}</span>
          <span className='kb-meta-pill'>{`投影关系 ${projected_graph.edges.length}`}</span>
          <span className='kb-meta-pill'>{current_view_label}</span>
          <span className='kb-meta-pill'>{GRAPH_VIEWPORT_MODE_LABELS[viewport_mode]}</span>
          {evidence_layer_active ? <span className='kb-meta-pill'>证据层</span> : null}
          {structure_layer_active ? <span className='kb-meta-pill'>结构层</span> : null}
        </div>

        <div className='kb-graph-stage-legend'>
          <span className='kb-graph-legend-item'>
            <i className='is-entity' />
            实体节点
          </span>
          <span className='kb-graph-legend-item'>
            <i className='is-edge' />
            语义关系
          </span>
          {evidence_layer_active ? (
            <>
              <span className='kb-graph-legend-item'>
                <i className='is-source' />
                来源节点
              </span>
              <span className='kb-graph-legend-item'>
                <i className='is-paragraph' />
                段落节点
              </span>
            </>
          ) : null}
        </div>

        {is_graph_loading ? <div className='kb-graph-loading'>正在刷新图谱...</div> : null}

        {left_drawer_mode ? (
          <aside className='kb-graph-drawer kb-graph-drawer-left'>
            <div className='kb-graph-drawer-card'>{render_left_drawer()}</div>
          </aside>
        ) : null}

        {inspector_open ? (
          <aside className='kb-graph-drawer kb-graph-drawer-right'>
            <div className='kb-graph-drawer-card'>{render_inspector()}</div>
          </aside>
        ) : null}
      </section>
    </section>
  );
}
