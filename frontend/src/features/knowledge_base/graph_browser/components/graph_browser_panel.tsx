import { useEffect, useMemo, useState, type FormEvent } from 'react';

import type { ResolvedTheme } from '../../../../theme';
import { GRAPH_VIEWPORT_MODE_LABELS, NODE_TYPE_LABELS, PREDICATE_SUGGESTIONS } from '../../shared/config/ui_constants';
import type { KnowledgeGraphNodeRecord } from '../../shared/types/knowledge_base_types';
import { use_graph_browser } from '../hooks/use_graph_browser';
import { JsonDetails, MetadataRows } from './graph_browser_detail_blocks';
import {
  collect_edge_import_rows,
  collect_node_import_rows,
  create_viewport_command,
  DEFAULT_PREDICATE,
  DENSITY_PRESETS,
  edge_action_copy,
  node_action_copy,
  node_option_label,
  selected_source_summary,
  type ViewportCommand,
} from './graph_browser_utils';
import { KnowledgeGraphCanvas } from './knowledge_graph_canvas';
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

const DEFAULT_RELATION_DRAFT: RelationDraft = {
  subject_node_id: '',
  predicate: DEFAULT_PREDICATE,
  object_node_id: '',
  weight: 0.9,
};

function normalize_keyword(value: string): string {
  return value.trim().toLowerCase();
}

function is_entity_node(node: KnowledgeGraphNodeRecord | null | undefined): node is KnowledgeGraphNodeRecord {
  return Boolean(node && node.type === 'entity');
}

export function GraphBrowserPanel(props: GraphBrowserPanelProps) {
  const { resolved_theme } = props;
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
    graph_controls_open,
    graph_inspector_open,
    active_graph_drawer,
    graph_viewport_mode,
    is_graph_loading,
    is_creating_node,
    is_creating_manual_relation,
    is_renaming_node,
    is_deleting_node,
    is_deleting_edge,
    set_selected_source_ids,
    set_include_paragraphs,
    set_density,
    set_graph_controls_open,
    set_graph_inspector_open,
    set_active_graph_drawer,
    set_graph_viewport_mode,
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
  const [viewport_command, set_viewport_command] = useState<ViewportCommand | null>(null);
  const [source_keyword, set_source_keyword] = useState('');
  const [node_keyword, set_node_keyword] = useState('');
  const [rename_value, set_rename_value] = useState('');
  const [create_label, set_create_label] = useState('');
  const [create_description, set_create_description] = useState('');
  const [relation_draft, set_relation_draft] = useState<RelationDraft>(DEFAULT_RELATION_DRAFT);

  const node_map = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);
  const selected_node = selected_node_id ? node_map.get(selected_node_id) ?? null : null;
  const selected_edge = selected_edge_id ? graph.edges.find((edge) => edge.id === selected_edge_id) ?? null : null;
  const source_scope_label = useMemo(() => selected_source_summary(selected_source_ids, sources), [selected_source_ids, sources]);
  const relation_node_options = useMemo(
    () => graph.nodes.filter((node) => node.type === 'entity').sort((left, right) => left.label.localeCompare(right.label, 'zh-CN')),
    [graph.nodes],
  );
  const searchable_nodes = useMemo(
    () => [...graph.nodes].sort((left, right) => left.label.localeCompare(right.label, 'zh-CN')),
    [graph.nodes],
  );
  const node_matches = useMemo(() => {
    const keyword = normalize_keyword(node_keyword);
    if (!keyword) {
      return searchable_nodes.slice(0, 12);
    }
    return searchable_nodes
      .filter((node) => `${node.label} ${node.type} ${node.id}`.toLowerCase().includes(keyword))
      .slice(0, 12);
  }, [node_keyword, searchable_nodes]);
  const filtered_sources = useMemo(() => {
    const keyword = normalize_keyword(source_keyword);
    if (!keyword) {
      return sources;
    }
    return sources.filter((source) =>
      `${source.name} ${source.summary ?? ''} ${source.source_kind}`.toLowerCase().includes(keyword),
    );
  }, [source_keyword, sources]);
  const left_drawer_mode =
    active_graph_drawer === 'filters' || active_graph_drawer === 'create-node' || active_graph_drawer === 'relation'
      ? active_graph_drawer
      : null;
  const inspector_open = active_graph_drawer === 'inspector' && graph_inspector_open && Boolean(selected_node_id || selected_edge_id);
  const selected_node_copy = node_detail ? node_action_copy(node_detail) : null;
  const selected_edge_copy = edge_detail ? edge_action_copy(edge_detail) : null;
  const selected_node_rows = useMemo(
    () => (node_detail ? collect_node_import_rows(node_detail.node.type, node_detail.node.metadata) : []),
    [node_detail],
  );
  const selected_edge_rows = useMemo(
    () => (edge_detail ? collect_edge_import_rows(edge_detail.edge.metadata) : []),
    [edge_detail],
  );
  const selected_edge_source_label = selected_edge ? node_map.get(selected_edge.source)?.label ?? selected_edge.source : '';
  const selected_edge_target_label = selected_edge ? node_map.get(selected_edge.target)?.label ?? selected_edge.target : '';
  const has_focus_target = Boolean(
    selected_node_id || selected_edge_id || highlighted_node_ids.length || highlighted_edge_ids.length,
  );

  useEffect(() => {
    if (node_detail) {
      set_rename_value(node_detail.node.label);
      set_graph_controls_open(false);
      set_graph_inspector_open(true);
      set_active_graph_drawer('inspector');
    }
  }, [node_detail, set_active_graph_drawer, set_graph_controls_open, set_graph_inspector_open]);

  useEffect(() => {
    if (edge_detail) {
      set_graph_controls_open(false);
      set_graph_inspector_open(true);
      set_active_graph_drawer('inspector');
    }
  }, [edge_detail, set_active_graph_drawer, set_graph_controls_open, set_graph_inspector_open]);

  useEffect(() => {
    if (!selected_node_id && !selected_edge_id && active_graph_drawer === 'inspector') {
      set_graph_inspector_open(false);
      set_active_graph_drawer(null);
    }
  }, [active_graph_drawer, selected_edge_id, selected_node_id, set_active_graph_drawer, set_graph_inspector_open]);

  function open_left_drawer(mode: 'filters' | 'create-node' | 'relation'): void {
    set_graph_controls_open(true);
    set_graph_inspector_open(false);
    set_active_graph_drawer(mode);
  }

  function close_left_drawer(): void {
    set_graph_controls_open(false);
    if (left_drawer_mode) {
      set_active_graph_drawer(null);
    }
  }

  function close_inspector(): void {
    set_graph_inspector_open(false);
    if (active_graph_drawer === 'inspector') {
      set_active_graph_drawer(null);
    }
  }

  function focus_selected(): void {
    set_graph_viewport_mode('focus-selection');
    set_viewport_command(create_viewport_command('focus-selection'));
  }

  function fit_all(): void {
    set_graph_viewport_mode('fit-all');
    set_viewport_command(create_viewport_command('fit-all'));
  }

  function handle_select_node(node_id: string): void {
    select_node(node_id);
    set_graph_controls_open(false);
    set_graph_inspector_open(true);
    set_active_graph_drawer('inspector');
    focus_selected();
  }

  function handle_select_edge(edge_id: string): void {
    select_edge(edge_id);
    set_graph_controls_open(false);
    set_graph_inspector_open(true);
    set_active_graph_drawer('inspector');
    focus_selected();
  }

  function handle_clear_selection(): void {
    clear_graph_selection();
    close_inspector();
  }

  function handle_clear_all(): void {
    set_node_keyword('');
    clear_graph_selection();
    clear_highlights();
    fit_all();
  }

  async function handle_refresh_graph(): Promise<void> {
    set_graph_viewport_mode('fit-all');
    await refresh_graph();
    set_viewport_command(create_viewport_command('fit-all'));
  }

  function handle_apply_search(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const first_match = node_matches[0];
    if (first_match) {
      handle_select_node(first_match.id);
    }
  }

  function handle_toggle_source(source_id: string): void {
    set_selected_source_ids((current) =>
      current.includes(source_id) ? current.filter((item) => item !== source_id) : [...current, source_id],
    );
  }

  async function handle_create_entity(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const label = create_label.trim();
    if (!label) {
      return;
    }
    await create_entity(label, {
      description: create_description.trim() || undefined,
      metadata: create_description.trim() ? { description: create_description.trim() } : undefined,
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
    if (!next_label || next_label === node_detail.node.label) {
      return;
    }
    await rename_node(node_detail.node.id, next_label);
  }

  async function handle_delete_selected_node(): Promise<void> {
    if (!node_detail || !selected_node_copy?.delete_allowed || !window.confirm(selected_node_copy.delete_message)) {
      return;
    }
    await delete_node(node_detail.node.id);
    close_inspector();
    fit_all();
  }

  async function handle_delete_selected_edge(): Promise<void> {
    if (!edge_detail || !selected_edge_copy?.delete_allowed || !window.confirm(selected_edge_copy.delete_message)) {
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
      predicate: edge_detail.edge.label || edge_detail.edge.type || DEFAULT_PREDICATE,
      object_node_id: edge_detail.edge.target,
      weight: edge_detail.edge.weight || 0.9,
    });
  }

  function relayout_graph(): void {
    set_layout_revision((current) => current + 1);
    fit_all();
  }

  return (
    <section className='kb-panel kb-graph-page'>
      <section className='kb-graph-toolbar'>
        <div className='kb-graph-toolbar-row'>
          <div className='kb-graph-toolbar-copy'>
            <span className='kb-context-label'>Knowledge Graph</span>
            <strong>图谱工作台</strong>
            <span className='kb-helper-text'>搜索、筛选、手动编辑和图谱浏览都收进同一个桌面工作区。</span>
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
            <label className='kb-form-field'>
              <span>节点搜索</span>
              <input
                list='kb-graph-node-search'
                onChange={(event) => set_node_keyword(event.target.value)}
                placeholder='输入节点名称、类型或 ID'
                value={node_keyword}
              />
            </label>
            <datalist id='kb-graph-node-search'>
              {node_matches.map((node) => (
                <option key={node.id} value={node.label}>
                  {node_option_label(node.id, graph)}
                </option>
              ))}
            </datalist>
            <button className='kb-secondary-button' type='submit'>
              定位
            </button>
          </form>

          <div className='kb-graph-toolbar-actions'>
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
            <button className='kb-secondary-button' onClick={() => set_viewport_command(create_viewport_command('zoom-in'))} type='button'>
              放大
            </button>
            <button className='kb-secondary-button' onClick={() => set_viewport_command(create_viewport_command('zoom-out'))} type='button'>
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
        <KnowledgeGraphCanvas
          edges={graph.edges}
          highlighted_edge_ids={highlighted_edge_ids}
          highlighted_node_ids={highlighted_node_ids}
          layout_revision={layout_revision}
          nodes={graph.nodes}
          on_clear_selection={handle_clear_selection}
          on_select_edge={handle_select_edge}
          on_select_node={handle_select_node}
          resolved_theme={resolved_theme}
          selected_edge_id={selected_edge_id}
          selected_node_id={selected_node_id}
          viewport_command={viewport_command}
          viewport_mode={graph_viewport_mode}
        />

        <div className='kb-graph-stage-badges'>
          <span className='kb-meta-pill'>{source_scope_label}</span>
          <span className='kb-meta-pill'>{`节点 ${graph.nodes.length}`}</span>
          <span className='kb-meta-pill'>{`关系 ${graph.edges.length}`}</span>
          <span className='kb-meta-pill'>{include_paragraphs ? '显示段落' : '隐藏段落'}</span>
          <span className='kb-meta-pill'>{GRAPH_VIEWPORT_MODE_LABELS[graph_viewport_mode]}</span>
        </div>

        <div className='kb-graph-stage-legend'>
          <span className='kb-graph-legend-item'>
            <i className='is-source' />
            来源节点
          </span>
          <span className='kb-graph-legend-item'>
            <i className='is-paragraph' />
            段落节点
          </span>
          <span className='kb-graph-legend-item'>
            <i className='is-entity' />
            实体节点
          </span>
          <span className='kb-graph-legend-item'>
            <i className='is-edge' />
            关系边
          </span>
        </div>

        {is_graph_loading ? <div className='kb-graph-loading'>正在刷新图谱...</div> : null}

        {left_drawer_mode && graph_controls_open ? (
          <aside className='kb-graph-drawer kb-graph-drawer-left'>
            <div className='kb-graph-drawer-card'>
              {left_drawer_mode === 'filters' ? (
                <>
                  <div className='kb-graph-drawer-head'>
                    <div>
                      <span className='kb-context-label'>Filters</span>
                      <h3>来源与显示</h3>
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
                      placeholder='按名称、摘要或类型搜索'
                      value={source_keyword}
                    />
                  </label>

                  <div className='kb-graph-source-list'>
                    {filtered_sources.map((source) => (
                      <label className='kb-graph-source-option' key={source.id}>
                        <input checked={selected_source_ids.includes(source.id)} onChange={() => handle_toggle_source(source.id)} type='checkbox' />
                        <div>
                          <strong>{source.name}</strong>
                          <span>{source.summary || source.source_kind}</span>
                        </div>
                      </label>
                    ))}
                    {!filtered_sources.length ? <div className='kb-helper-text'>没有匹配的来源。</div> : null}
                  </div>

                  <label className='kb-check-field'>
                    <input checked={include_paragraphs} onChange={(event) => set_include_paragraphs(event.target.checked)} type='checkbox' />
                    <span>显示段落节点</span>
                  </label>

                  <label className='kb-form-field'>
                    <span>{`图谱密度 ${density}%`}</span>
                    <input max={100} min={12} onChange={(event) => set_density(Number(event.target.value))} type='range' value={density} />
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
              ) : null}

              {left_drawer_mode === 'create-node' ? (
                <form className='kb-graph-form' onSubmit={(event) => void handle_create_entity(event)}>
                  <div className='kb-graph-drawer-head'>
                    <div>
                      <span className='kb-context-label'>Create Node</span>
                      <h3>新建手工实体</h3>
                      <p>创建后会自动选中该实体，并可继续在右侧详情抽屉里编辑。</p>
                    </div>
                    <button className='kb-secondary-button' onClick={close_left_drawer} type='button'>
                      关闭
                    </button>
                  </div>

                  <label className='kb-form-field'>
                    <span>实体名称</span>
                    <input onChange={(event) => set_create_label(event.target.value)} placeholder='例如：项目 Alpha' value={create_label} />
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
                    <button className='kb-primary-button' disabled={is_creating_node || !create_label.trim()} type='submit'>
                      {is_creating_node ? '创建中...' : '创建实体'}
                    </button>
                  </div>
                </form>
              ) : null}

              {left_drawer_mode === 'relation' ? (
                <form className='kb-graph-form' onSubmit={(event) => void handle_create_relation(event)}>
                  <div className='kb-graph-drawer-head'>
                    <div>
                      <span className='kb-context-label'>Create Relation</span>
                      <h3>补关系</h3>
                      <p>手动补边仅允许实体与实体之间建立关系。</p>
                    </div>
                    <button className='kb-secondary-button' onClick={close_left_drawer} type='button'>
                      关闭
                    </button>
                  </div>

                  {is_entity_node(selected_node) ? (
                    <div className='kb-button-row'>
                      <button className='kb-chip' onClick={() => assign_relation_endpoint('subject', selected_node.id)} type='button'>
                        用当前选中作为起点
                      </button>
                      <button className='kb-chip' onClick={() => assign_relation_endpoint('object', selected_node.id)} type='button'>
                        用当前选中作为终点
                      </button>
                    </div>
                  ) : null}

                  <label className='kb-form-field'>
                    <span>起点实体</span>
                    <select
                      onChange={(event) => set_relation_draft((current) => ({ ...current, subject_node_id: event.target.value }))}
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
                      onChange={(event) => set_relation_draft((current) => ({ ...current, predicate: event.target.value }))}
                      placeholder='例如：依赖 / 归属 / 引用'
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
                      onChange={(event) => set_relation_draft((current) => ({ ...current, object_node_id: event.target.value }))}
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
                      onChange={(event) => set_relation_draft((current) => ({ ...current, weight: Number(event.target.value) }))}
                      step={0.05}
                      type='range'
                      value={relation_draft.weight}
                    />
                  </label>

                  <div className='kb-helper-text'>{`当前共有 ${manual_relations.length} 条手动关系。`}</div>

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
                      {is_creating_manual_relation ? '提交中...' : '创建关系'}
                    </button>
                  </div>
                </form>
              ) : null}
            </div>
          </aside>
        ) : null}

        {inspector_open ? (
          <aside className='kb-graph-drawer kb-graph-drawer-right'>
            <div className='kb-graph-drawer-card'>
              {!node_detail && !edge_detail ? (
                <div className='kb-graph-drawer-loading'>
                  <span className='kb-context-label'>Inspector</span>
                  <strong>正在加载详情...</strong>
                  <span className='kb-helper-text'>详情面板会根据当前选中的节点或边自动切换。</span>
                </div>
              ) : null}

              {node_detail ? (
                <div className='kb-graph-inspector-content'>
                  <div className='kb-graph-drawer-head'>
                    <div>
                      <span className='kb-context-label'>Inspector</span>
                      <h3>{node_detail.node.label}</h3>
                      <p>{NODE_TYPE_LABELS[node_detail.node.type] ?? node_detail.node.type}</p>
                    </div>
                    <button className='kb-secondary-button' onClick={close_inspector} type='button'>
                      关闭
                    </button>
                  </div>

                  <div className='kb-meta-strip'>
                    <span className='kb-meta-pill'>{`段落 ${node_detail.paragraphs.length}`}</span>
                    <span className='kb-meta-pill'>{`关系 ${node_detail.relations.length}`}</span>
                  </div>

                  {selected_node_copy?.rename_allowed ? (
                    <form className='kb-graph-inline-form' onSubmit={(event) => void handle_rename_node(event)}>
                      <input onChange={(event) => set_rename_value(event.target.value)} value={rename_value} />
                      <button className='kb-secondary-button' disabled={is_renaming_node || !rename_value.trim()} type='submit'>
                        {is_renaming_node ? '保存中...' : '重命名'}
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
                        {is_deleting_node ? '删除中...' : selected_node_copy.delete_label}
                      </button>
                    ) : null}
                  </div>

                  {!selected_node_copy?.rename_allowed && !selected_node_copy?.delete_allowed && !selected_node_copy?.relation_allowed ? (
                    <div className='kb-helper-text'>该节点当前仅支持查看详情，不支持手动编辑。</div>
                  ) : null}

                  <MetadataRows rows={selected_node_rows} />
                  <JsonDetails title='节点元数据' value={node_detail.node.metadata} />
                  {node_detail.source ? <JsonDetails title='来源信息' value={node_detail.source} /> : null}
                  {node_detail.paragraphs.length ? <JsonDetails title='关联段落' value={{ paragraphs: node_detail.paragraphs }} /> : null}
                  {node_detail.relations.length ? <JsonDetails title='关联关系' value={{ relations: node_detail.relations }} /> : null}
                </div>
              ) : null}

              {edge_detail ? (
                <div className='kb-graph-inspector-content'>
                  <div className='kb-graph-drawer-head'>
                    <div>
                      <span className='kb-context-label'>Inspector</span>
                      <h3>{edge_detail.edge.label}</h3>
                      <p>{edge_detail.edge.type}</p>
                    </div>
                    <button className='kb-secondary-button' onClick={close_inspector} type='button'>
                      关闭
                    </button>
                  </div>

                  <div className='kb-meta-strip'>
                    <span className='kb-meta-pill'>{`起点 ${selected_edge_source_label}`}</span>
                    <span className='kb-meta-pill'>{`终点 ${selected_edge_target_label}`}</span>
                    <span className='kb-meta-pill'>{`权重 ${edge_detail.edge.weight}`}</span>
                  </div>

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
                        {is_deleting_edge ? '删除中...' : '删除关系'}
                      </button>
                    ) : null}
                  </div>

                  {!selected_edge_copy?.delete_allowed && !selected_edge_copy?.copy_allowed ? (
                    <div className='kb-helper-text'>结构关系当前仅支持查看详情，不支持手动删除。</div>
                  ) : null}

                  <MetadataRows rows={selected_edge_rows} />
                  <JsonDetails title='关系元数据' value={edge_detail.edge.metadata} />
                  {edge_detail.source ? <JsonDetails title='来源信息' value={edge_detail.source} /> : null}
                  {edge_detail.paragraph ? <JsonDetails title='段落信息' value={edge_detail.paragraph} /> : null}
                </div>
              ) : null}
            </div>
          </aside>
        ) : null}
      </section>
    </section>
  );
}
