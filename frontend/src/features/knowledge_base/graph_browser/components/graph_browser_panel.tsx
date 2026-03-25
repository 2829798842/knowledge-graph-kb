/**
 * 图谱浏览面板。
 */

import { useDeferredValue, useEffect, useState } from 'react';

import type { ResolvedTheme } from '../../../../theme';
import {
  get_input_mode_label,
  get_knowledge_type_label,
  get_strategy_label,
  NODE_TYPE_LABELS,
  PREDICATE_SUGGESTIONS,
} from '../../shared/config/ui_constants';
import type { KnowledgeGraphRecord, SourceRecord } from '../../shared/types/knowledge_base_types';
import { use_graph_browser } from '../hooks/use_graph_browser';
import '../styles/graph_browser_panel.css';
import { KnowledgeGraphCanvas } from './knowledge_graph_canvas';

interface GraphBrowserPanelProps {
  resolved_theme: ResolvedTheme;
}

function node_option_label(node_id: string, graph: KnowledgeGraphRecord): string {
  const node = graph.nodes.find((current_node) => current_node.id === node_id);
  if (!node) {
    return node_id;
  }
  return `${NODE_TYPE_LABELS[node.type] ?? node.type} - ${node.label}`;
}

function format_metadata_value(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => format_metadata_value(item)).join(', ');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return '';
}

function merge_node_metadata(metadata: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!metadata) {
    return {};
  }
  const nested =
    metadata.metadata && typeof metadata.metadata === 'object' && !Array.isArray(metadata.metadata)
      ? (metadata.metadata as Record<string, unknown>)
      : {};
  return { ...metadata, ...nested };
}

function collect_node_import_rows(node_type: string, metadata: Record<string, unknown> | undefined): [string, string][] {
  const merged = merge_node_metadata(metadata);
  const rows: [string, string][] = [];
  const file_type = format_metadata_value(merged.source_file_type || merged.file_type);
  const file_name = format_metadata_value(merged.name);
  const source_kind = format_metadata_value(merged.source_kind);
  const input_mode = format_metadata_value(merged.input_mode);
  const strategy = format_metadata_value(
    merged.detected_strategy || merged.strategy || merged.source_strategy || merged.import_strategy,
  );
  if (file_type) {
    rows.push(['文件类型', file_type]);
  }
  if (file_name) {
    rows.push(['文件名', file_name]);
  }
  if (strategy) {
    rows.push(['导入策略', get_strategy_label(strategy)]);
  }
  if (source_kind) {
    rows.push(['来源类型', get_input_mode_label(source_kind)]);
  }
  if (input_mode) {
    rows.push(['导入方式', get_input_mode_label(input_mode)]);
  }

  if (node_type === 'paragraph') {
    const knowledge_type = format_metadata_value(merged.knowledge_type);
    const worksheet_name = format_metadata_value(merged.worksheet_name);
    const is_spreadsheet = format_metadata_value(merged.is_spreadsheet).toLowerCase() === 'true';
    if (is_spreadsheet) {
      rows.push(['表格来源', '是']);
    }
    if (knowledge_type) {
      rows.push(['知识类型', get_knowledge_type_label(knowledge_type)]);
    }
    if (worksheet_name) {
      rows.push(['工作表', worksheet_name]);
    }
  }

  if (node_type === 'source' || node_type === 'workbook') {
    const spreadsheet_sheets = Array.isArray(merged.spreadsheet_sheets)
      ? merged.spreadsheet_sheets.map((sheet) => format_metadata_value(sheet)).filter((sheet) => sheet.length)
      : [];
    if (spreadsheet_sheets.length > 0) {
      rows.push(['工作表列表', spreadsheet_sheets.join(', ')]);
    }
  }

  const source_id = format_metadata_value(merged.source_id);
  if (source_id) {
    rows.push(['来源 ID', source_id]);
  }
  return rows;
}

function collect_edge_import_rows(metadata: Record<string, unknown> | undefined): [string, string][] {
  const rows: [string, string][] = [];
  if (!metadata) {
    return rows;
  }
  const source_id = format_metadata_value(metadata.source_id);
  if (source_id) {
    rows.push(['来源 ID', source_id]);
  }
  const paragraph_id = format_metadata_value(metadata.paragraph_id);
  if (paragraph_id) {
    rows.push(['段落 ID', paragraph_id]);
  }
  return rows;
}

function selected_source_summary(selected_source_ids: string[], sources: SourceRecord[]): string {
  if (!selected_source_ids.length) {
    return '全部来源';
  }
  const selected_names = sources
    .filter((source) => selected_source_ids.includes(source.id))
    .map((source) => source.name);
  if (selected_names.length <= 3) {
    return selected_names.join('、');
  }
  return `${selected_names.slice(0, 3).join('、')} 等 ${selected_names.length} 个`;
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
    highlighted_node_ids,
    highlighted_edge_ids,
    is_graph_loading,
    is_creating_manual_relation,
    set_selected_source_ids,
    set_include_paragraphs,
    set_density,
    select_node,
    select_edge,
    clear_graph_selection,
    create_relation,
    remove_manual_relation,
    clear_highlights,
  } = use_graph_browser();

  const [source_filter_text, set_source_filter_text] = useState<string>('');
  const [subject_node_id, set_subject_node_id] = useState<string>('');
  const [predicate, set_predicate] = useState<string>(PREDICATE_SUGGESTIONS[0] ?? '提及');
  const [object_node_id, set_object_node_id] = useState<string>('');
  const [weight, set_weight] = useState<number>(1);
  const deferred_source_filter: string = useDeferredValue(source_filter_text.trim().toLowerCase());
  const node_import_rows: [string, string][] = node_detail
    ? collect_node_import_rows(node_detail.node.type, node_detail.node.metadata)
    : [];
  const edge_import_rows: [string, string][] = edge_detail ? collect_edge_import_rows(edge_detail.edge.metadata) : [];

  const filtered_sources: SourceRecord[] = sources.filter((source) => {
    if (!deferred_source_filter) {
      return true;
    }
    const haystack: string = `${source.name} ${source.summary ?? ''} ${source.source_kind}`.toLowerCase();
    return haystack.includes(deferred_source_filter);
  });
  const relation_node_options = [...graph.nodes].sort((left_node, right_node) =>
    left_node.label.localeCompare(right_node.label, 'zh-CN'),
  );
  const predicate_template_value: string = PREDICATE_SUGGESTIONS.includes(predicate) ? predicate : '__custom__';

  useEffect(() => {
    if (!selected_node_id) {
      return;
    }
    if (!subject_node_id) {
      set_subject_node_id(selected_node_id);
      return;
    }
    if (subject_node_id !== selected_node_id && !object_node_id) {
      set_object_node_id(selected_node_id);
    }
  }, [object_node_id, selected_node_id, subject_node_id]);

  useEffect(() => {
    if (subject_node_id && !graph.nodes.some((node) => node.id === subject_node_id)) {
      set_subject_node_id('');
    }
    if (object_node_id && !graph.nodes.some((node) => node.id === object_node_id)) {
      set_object_node_id('');
    }
  }, [graph.nodes, object_node_id, subject_node_id]);

  return (
    <section className='kb-panel kb-graph-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>图谱浏览</h2>
          <p>图谱页已经改成宽屏优先布局，优先把空间留给 Cytoscape 画布，筛选和详情放到两侧控制区。</p>
        </div>
      </header>

      <div className='kb-panel-split kb-panel-split-graph'>
        <aside className='kb-sidebar kb-graph-sidebar'>
          <div className='kb-filter-card'>
            <h3>图谱过滤</h3>
            <p>{`当前来源：${selected_source_summary(selected_source_ids, sources)}`}</p>

            <label className='kb-form-field'>
              <span>筛选来源</span>
              <input
                onChange={(event) => set_source_filter_text(event.target.value)}
                placeholder='按名称、摘要或类型过滤'
                type='search'
                value={source_filter_text}
              />
            </label>

            <label className='kb-form-field'>
              <span>来源选择</span>
              <select
                className='kb-graph-source-select'
                multiple
                onChange={(event) =>
                  set_selected_source_ids(Array.from(event.target.selectedOptions).map((option) => option.value))
                }
                size={Math.min(Math.max(filtered_sources.length, 6), 10)}
                value={selected_source_ids}
              >
                {filtered_sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name}
                  </option>
                ))}
              </select>
              <span className='kb-helper-text'>按住 Ctrl 或 Command 可以多选；不选时默认显示全部来源。</span>
            </label>

            <label className='kb-form-field'>
              <span>图谱密度</span>
              <input
                max={100}
                min={5}
                onChange={(event) => set_density(Number(event.target.value))}
                type='range'
                value={density}
              />
              <strong>{density}%</strong>
            </label>

            <label className='kb-check-field'>
              <input
                checked={include_paragraphs}
                onChange={(event) => set_include_paragraphs(event.target.checked)}
                type='checkbox'
              />
              <span>显示段落节点</span>
            </label>

            <div className='kb-button-row'>
              <button className='kb-secondary-button' onClick={() => set_selected_source_ids([])} type='button'>
                显示全部来源
              </button>
              <button className='kb-secondary-button' onClick={clear_highlights} type='button'>
                清空高亮
              </button>
            </div>
          </div>

          <div className='kb-filter-card'>
            <h3>手动关系</h3>
            <p>通过下拉选择节点和常用关系，为图谱补充人工关系。</p>

            <label className='kb-form-field'>
              <span>起点节点</span>
              <select onChange={(event) => set_subject_node_id(event.target.value)} value={subject_node_id}>
                <option value=''>选择起点节点</option>
                {relation_node_options.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node_option_label(node.id, graph)}
                  </option>
                ))}
              </select>
            </label>

            <label className='kb-form-field'>
              <span>关系模板</span>
              <select
                onChange={(event) => {
                  if (event.target.value !== '__custom__') {
                    set_predicate(event.target.value);
                  }
                }}
                value={predicate_template_value}
              >
                {PREDICATE_SUGGESTIONS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
                <option value='__custom__'>自定义输入</option>
              </select>
            </label>

            <label className='kb-form-field'>
              <span>关系名称</span>
              <input onChange={(event) => set_predicate(event.target.value)} type='text' value={predicate} />
            </label>

            <label className='kb-form-field'>
              <span>终点节点</span>
              <select onChange={(event) => set_object_node_id(event.target.value)} value={object_node_id}>
                <option value=''>选择终点节点</option>
                {relation_node_options.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node_option_label(node.id, graph)}
                  </option>
                ))}
              </select>
            </label>

            <label className='kb-form-field'>
              <span>权重</span>
              <input
                max={5}
                min={0.1}
                onChange={(event) => set_weight(Number(event.target.value))}
                step={0.1}
                type='number'
                value={weight}
              />
            </label>

            <div className='kb-button-row'>
              <button
                className='kb-secondary-button'
                disabled={!selected_node_id}
                onClick={() => {
                  if (selected_node_id) {
                    set_subject_node_id(selected_node_id);
                  }
                }}
                type='button'
              >
                将当前节点设为起点
              </button>
              <button
                className='kb-secondary-button'
                disabled={!selected_node_id}
                onClick={() => {
                  if (selected_node_id) {
                    set_object_node_id(selected_node_id);
                  }
                }}
                type='button'
              >
                将当前节点设为终点
              </button>
            </div>

            <button
              className='kb-primary-button'
              disabled={
                is_creating_manual_relation ||
                !subject_node_id.trim() ||
                !predicate.trim() ||
                !object_node_id.trim() ||
                subject_node_id === object_node_id
              }
              onClick={() => void create_relation(subject_node_id, predicate.trim(), object_node_id, weight)}
              type='button'
            >
              {is_creating_manual_relation ? '创建中...' : '创建手动关系'}
            </button>
          </div>
        </aside>

        <div className='kb-graph-main'>
          <div className='kb-meta-strip'>
            <span className='kb-meta-pill'>{`节点 ${graph.nodes.length}`}</span>
            <span className='kb-meta-pill'>{`关系 ${graph.edges.length}`}</span>
            <span className='kb-meta-pill'>{selected_source_ids.length ? `已筛选 ${selected_source_ids.length} 个来源` : '显示全部来源'}</span>
            <span className='kb-meta-pill'>{is_graph_loading ? '图谱刷新中...' : '图谱已就绪'}</span>
          </div>

          <KnowledgeGraphCanvas
            edges={graph.edges}
            highlighted_edge_ids={highlighted_edge_ids}
            highlighted_node_ids={highlighted_node_ids}
            nodes={graph.nodes}
            on_clear_selection={clear_graph_selection}
            on_select_edge={select_edge}
            on_select_node={select_node}
            resolved_theme={resolved_theme}
            selected_edge_id={selected_edge_id}
            selected_node_id={selected_node_id}
          />

          <div className='kb-legend-row'>
            <span className='kb-legend-item'>来源节点</span>
            <span className='kb-legend-item'>段落节点</span>
            <span className='kb-legend-item'>实体节点</span>
            <span className='kb-legend-item'>关系连线</span>
          </div>
        </div>

        <aside className='kb-detail-panel kb-graph-details'>
          <div className='kb-detail-card'>
            <h3>当前详情</h3>
            {node_detail ? (
              <>
                <strong>{node_detail.node.label}</strong>
                <span>{NODE_TYPE_LABELS[node_detail.node.type] ?? node_detail.node.type}</span>
                <div className='kb-meta-strip'>
                  <span className='kb-meta-pill'>{`段落 ${node_detail.paragraphs.length}`}</span>
                  <span className='kb-meta-pill'>{`关系 ${node_detail.relations.length}`}</span>
                </div>
                <div className='kb-button-row'>
                  <button className='kb-secondary-button' onClick={() => set_subject_node_id(node_detail.node.id)} type='button'>
                    设为起点
                  </button>
                  <button className='kb-secondary-button' onClick={() => set_object_node_id(node_detail.node.id)} type='button'>
                    设为终点
                  </button>
                </div>
                {node_import_rows.length ? (
                  <div className='kb-meta-strip'>
                    {node_import_rows.map(([item_key, item_value]) => (
                      <span className='kb-helper-text' key={`${item_key}-${item_value}`}>
                        {`${item_key}：${item_value}`}
                      </span>
                    ))}
                  </div>
                ) : null}
                <pre>{JSON.stringify(node_detail.node.metadata, null, 2)}</pre>
              </>
            ) : null}

            {edge_detail ? (
              <>
                <strong>{edge_detail.edge.label}</strong>
                <span>{edge_detail.edge.type}</span>
                {edge_import_rows.length ? (
                  <div className='kb-meta-strip'>
                    {edge_import_rows.map(([item_key, item_value]) => (
                      <span className='kb-helper-text' key={`${item_key}-${item_value}`}>
                        {`${item_key}：${item_value}`}
                      </span>
                    ))}
                  </div>
                ) : null}
                <pre>{JSON.stringify(edge_detail.edge.metadata, null, 2)}</pre>
              </>
            ) : null}

            {!node_detail && !edge_detail ? <span>点击图谱中的节点或连线后，这里会显示详情。</span> : null}
          </div>

          <div className='kb-detail-card'>
            <h3>手动关系列表</h3>
            <div className='kb-relation-list'>
              {manual_relations.map((relation) => (
                <div className='kb-inline-card' key={relation.id}>
                  <strong>{relation.predicate}</strong>
                  <span>{`${node_option_label(relation.subject_node_id, graph)} -> ${node_option_label(relation.object_node_id, graph)}`}</span>
                  <span>{`权重 ${relation.weight.toFixed(1)}`}</span>
                  <button className='kb-secondary-button' onClick={() => void remove_manual_relation(relation.id)} type='button'>
                    删除
                  </button>
                </div>
              ))}
              {!manual_relations.length ? <span>当前还没有手动关系。</span> : null}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
