import { describe, expect, it } from 'vitest';

import {
  resolve_edge_alpha,
  resolve_label_priority_node_ids,
  resolve_node_fill_alpha,
  should_show_edge_label,
  should_show_node_label,
} from './graph_readability';
import type { RenderEdge, RenderNode } from './graph_render_types';

function create_node(overrides: Partial<RenderNode> = {}): RenderNode {
  return {
    id: overrides.id ?? 'node-1',
    type: overrides.type ?? 'entity',
    label: overrides.label ?? '节点 1',
    display_label: overrides.display_label ?? overrides.label ?? '节点 1',
    short_label: overrides.short_label ?? '节点 1',
    kind_label: overrides.kind_label ?? '实体',
    source_name: overrides.source_name ?? null,
    evidence_count: overrides.evidence_count ?? 0,
    size: overrides.size ?? 1,
    score: overrides.score ?? null,
    layer_mode: overrides.layer_mode ?? 'semantic',
    is_structural: overrides.is_structural ?? false,
    radius: overrides.radius ?? 14,
    color: overrides.color ?? 0x336699,
    searchable_text: overrides.searchable_text ?? '节点 1 实体',
    metadata: overrides.metadata ?? {},
  };
}

function create_edge(overrides: Partial<RenderEdge> = {}): RenderEdge {
  return {
    id: overrides.id ?? 'edge-1',
    source: overrides.source ?? 'node-1',
    target: overrides.target ?? 'node-2',
    type: overrides.type ?? 'relation',
    label: overrides.label ?? '关联',
    display_label: overrides.display_label ?? overrides.label ?? '关联',
    short_label: overrides.short_label ?? '关联',
    relation_kind_label: overrides.relation_kind_label ?? '抽取关系',
    source_name: overrides.source_name ?? null,
    evidence_paragraph_id: overrides.evidence_paragraph_id ?? null,
    weight: overrides.weight ?? 0.9,
    layer_mode: overrides.layer_mode ?? 'semantic',
    is_structural: overrides.is_structural ?? false,
    color: overrides.color ?? 0x7aa7c7,
    metadata: overrides.metadata ?? {},
  };
}

describe('graph_readability', () => {
  it('limits global labels to a small semantic priority set', () => {
    const nodes = Array.from({ length: 20 }, (_, index) =>
      create_node({
        id: `entity-${index + 1}`,
        label: `实体 ${index + 1}`,
        display_label: `实体 ${index + 1}`,
        evidence_count: index === 0 ? 12 : index === 1 ? 9 : 0,
        radius: index === 2 ? 20 : 14,
      }),
    );
    nodes.push(
      create_node({
        id: 'paragraph-1',
        type: 'paragraph',
        label: '段落 1',
        display_label: '段落 1',
        kind_label: '段落',
        layer_mode: 'evidence',
        is_structural: true,
      }),
    );
    const edges = [
      create_edge({ id: 'e-1', source: 'entity-1', target: 'entity-2' }),
      create_edge({ id: 'e-2', source: 'entity-1', target: 'entity-3' }),
      create_edge({ id: 'e-3', source: 'entity-2', target: 'entity-4' }),
    ];

    const priority_ids = resolve_label_priority_node_ids(nodes, edges);

    expect(priority_ids.has('entity-1')).toBe(true);
    expect(priority_ids.has('entity-2')).toBe(true);
    expect(priority_ids.has('paragraph-1')).toBe(false);
    expect(priority_ids.size).toBeLessThanOrEqual(8);
  });

  it('shows labels only for emphasized or priority semantic nodes in large graphs', () => {
    const normal_node = create_node({ id: 'entity-normal', evidence_count: 0, radius: 14 });
    const priority_node = create_node({ id: 'entity-priority', evidence_count: 10, radius: 18 });
    const context = {
      graph_view_mode: 'global' as const,
      total_node_count: 120,
      has_context: false,
      selected_node_id: null,
      selected_edge_id: null,
      selected_related_node_ids: new Set<string>(),
      highlighted_node_ids: new Set<string>(),
      highlighted_edge_ids: new Set<string>(),
      highlighted_edge_count: 0,
      label_priority_node_ids: new Set<string>(['entity-priority']),
    };

    expect(should_show_node_label(normal_node, context)).toBe(false);
    expect(should_show_node_label(priority_node, context)).toBe(true);
  });

  it('never shows non-semantic labels by default and keeps them visually weak', () => {
    const evidence_node = create_node({
      id: 'paragraph-1',
      type: 'paragraph',
      label: '段落 1',
      display_label: '段落 1',
      kind_label: '段落',
      layer_mode: 'evidence',
      is_structural: true,
    });
    const context = {
      graph_view_mode: 'global' as const,
      total_node_count: 120,
      has_context: false,
      selected_node_id: null,
      selected_edge_id: null,
      selected_related_node_ids: new Set<string>(),
      highlighted_node_ids: new Set<string>(),
      highlighted_edge_ids: new Set<string>(),
      highlighted_edge_count: 0,
      label_priority_node_ids: new Set<string>(),
    };

    expect(should_show_node_label(evidence_node, context)).toBe(false);
    expect(resolve_node_fill_alpha(evidence_node, context)).toBeLessThan(0.2);
  });

  it('shows edge labels only for selected edges or very small local contexts', () => {
    const edge = create_edge({ id: 'edge-highlighted' });
    const base_context = {
      graph_view_mode: 'local' as const,
      total_node_count: 80,
      has_context: true,
      selected_node_id: 'node-1',
      selected_edge_id: null,
      selected_related_node_ids: new Set<string>(['node-1', 'node-2']),
      highlighted_node_ids: new Set<string>(['node-1', 'node-2']),
      highlighted_edge_ids: new Set<string>(['edge-highlighted']),
      label_priority_node_ids: new Set<string>(),
    };

    expect(should_show_edge_label(edge, { ...base_context, highlighted_edge_count: 3 })).toBe(true);
    expect(should_show_edge_label(edge, { ...base_context, highlighted_edge_count: 7 })).toBe(false);
    expect(
      should_show_edge_label(edge, {
        ...base_context,
        selected_edge_id: 'edge-highlighted',
        highlighted_edge_count: 7,
      }),
    ).toBe(true);
  });

  it('keeps non-semantic edges weak even when evidence and structure layers are open', () => {
    const structural_edge = create_edge({
      id: 'edge-structure',
      layer_mode: 'structure',
      is_structural: true,
    });
    const context = {
      graph_view_mode: 'global' as const,
      total_node_count: 50,
      has_context: false,
      selected_node_id: null,
      selected_edge_id: null,
      selected_related_node_ids: new Set<string>(),
      highlighted_node_ids: new Set<string>(),
      highlighted_edge_ids: new Set<string>(),
      highlighted_edge_count: 0,
      label_priority_node_ids: new Set<string>(),
    };

    expect(resolve_edge_alpha(structural_edge, context)).toBeLessThan(0.1);
    expect(should_show_edge_label(structural_edge, context)).toBe(false);
  });

  it('keeps semantic edges readable in global mode', () => {
    const semantic_edge = create_edge({
      id: 'edge-semantic',
      layer_mode: 'semantic',
      is_structural: false,
    });
    const context = {
      graph_view_mode: 'global' as const,
      total_node_count: 120,
      has_context: false,
      selected_node_id: null,
      selected_edge_id: null,
      selected_related_node_ids: new Set<string>(),
      highlighted_node_ids: new Set<string>(),
      highlighted_edge_ids: new Set<string>(),
      highlighted_edge_count: 0,
      label_priority_node_ids: new Set<string>(),
    };

    expect(resolve_edge_alpha(semantic_edge, context)).toBeGreaterThanOrEqual(0.3);
  });
});
