/**
 * 模块名称：features/knowledge_base/components/graph_canvas/graph_canvas
 * 主要功能：渲染知识图谱 Cytoscape 画布，并处理节点高亮、选中与视口聚焦。
 */

import { useEffect, useRef } from 'react';
import cytoscape, { type Core, type ElementDefinition, type StylesheetJson } from 'cytoscape';

import type { ResolvedTheme } from '../../../../theme/theme_types';
import type { GraphEdgeRecord, GraphNodeRecord } from '../../types/knowledge_base';
import { get_edge_type_label } from '../../utils/label_utils';

/**
 * 图谱画布组件属性。
 */
interface GraphCanvasProps {
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
  selected_node_id: string | null;
  selected_edge_id: string | null;
  highlighted_node_ids: string[];
  highlighted_edge_ids: string[];
  resolved_theme: ResolvedTheme;
  on_node_select: (node: GraphNodeRecord) => void;
  on_edge_select: (edge: GraphEdgeRecord) => void;
  on_clear_selection: () => void;
}

const NODE_PALETTE: Record<string, string> = {
  document: '#c67c2f',
  chunk: '#0f766e',
  entity: '#154d71',
};

const EDGE_PALETTE: Record<string, string> = {
  contains: '#d6a160',
  semantic: '#1c9a84',
  mentions: '#3a7ca5',
  manual: '#d14d72',
};

const NODE_SIZE_BY_TYPE: Record<string, number> = {
  document: 68,
  chunk: 44,
  entity: 54,
};

/**
 * 获取图谱画布样式。
 *
 * @param resolved_theme - 当前实际主题。
 * @returns Cytoscape 样式定义。
 */
function build_cytoscape_styles(resolved_theme: ResolvedTheme): StylesheetJson {
  const text_color: string = resolved_theme === 'dark' ? '#eff7f5' : '#f5f7f7';
  const border_color: string = resolved_theme === 'dark' ? '#0f1e28' : '#fcfaf4';
  const edge_text_color: string = resolved_theme === 'dark' ? '#bccbd5' : '#6e5f48';
  const overlay_color: string = resolved_theme === 'dark' ? '#f2d48b' : '#ffffff';

  const styles: StylesheetJson = [
    {
      selector: 'node',
      style: {
        label: 'data(label)',
        'font-size': '11px',
        'text-wrap': 'wrap',
        'text-max-width': '110px',
        'text-valign': 'center',
        'text-halign': 'center',
        color: text_color,
        'background-color': 'data(color)',
        width: 'data(size)',
        height: 'data(size)',
        'border-width': 2,
        'border-color': border_color,
      },
    },
    {
      selector: 'edge',
      style: {
        label: 'data(edge_label)',
        'font-size': '9px',
        color: edge_text_color,
        width: 'mapData(weight, 0, 2, 1, 5)',
        'line-color': 'data(color)',
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': 'data(color)',
      },
    },
    {
      selector: '.highlighted',
      style: {
        'border-width': 4,
        'border-color': '#f8d66d',
        'line-color': '#f8d66d',
        'target-arrow-color': '#f8d66d',
        opacity: 1,
      },
    },
    {
      selector: '.muted',
      style: {
        opacity: 0.2,
      },
    },
    {
      selector: '.selected',
      style: {
        'overlay-color': overlay_color,
        'overlay-opacity': 0.16,
        'overlay-padding': '12px',
      },
    },
  ];

  return styles;
}

/**
 * 将业务节点和边转换为 Cytoscape 元素。
 *
 * @param nodes - 图谱节点列表。
 * @param edges - 图谱边列表。
 * @returns Cytoscape 可识别的元素定义列表。
 */
function to_cytoscape_elements(
  nodes: GraphNodeRecord[],
  edges: GraphEdgeRecord[],
): ElementDefinition[] {
  return [
    ...nodes.map((node) => ({
      group: 'nodes' as const,
      data: {
        ...node,
        color: NODE_PALETTE[node.type] ?? '#607d8b',
        size: NODE_SIZE_BY_TYPE[node.type] ?? 52,
      },
    })),
    ...edges.map((edge) => ({
      group: 'edges' as const,
      data: {
        ...edge,
        edge_label: get_edge_type_label(edge.type),
        color: EDGE_PALETTE[edge.type] ?? '#7c7c7c',
      },
    })),
  ];
}

/**
 * 渲染图谱画布。
 *
 * @param props - 组件属性。
 * @returns 图谱画布组件。
 */
export function GraphCanvas(props: GraphCanvasProps) {
  const {
    nodes,
    edges,
    selected_node_id,
    selected_edge_id,
    highlighted_node_ids,
    highlighted_edge_ids,
    resolved_theme,
    on_node_select,
    on_edge_select,
    on_clear_selection,
  } = props;
  const container_ref = useRef<HTMLDivElement | null>(null);
  const cy_ref = useRef<Core | null>(null);
  const handlers_ref = useRef({
    on_node_select,
    on_edge_select,
    on_clear_selection,
  });

  useEffect(() => {
    handlers_ref.current = {
      on_node_select,
      on_edge_select,
      on_clear_selection,
    };
  }, [on_node_select, on_edge_select, on_clear_selection]);

  useEffect(() => {
    if (!container_ref.current || cy_ref.current) {
      return;
    }

    const cy: Core = cytoscape({
      container: container_ref.current,
      style: build_cytoscape_styles(resolved_theme),
    });

    cy.on('tap', 'node', (event) => {
      handlers_ref.current.on_node_select(event.target.data() as GraphNodeRecord);
    });
    cy.on('tap', 'edge', (event) => {
      handlers_ref.current.on_edge_select(event.target.data() as GraphEdgeRecord);
    });
    cy.on('tap', (event) => {
      if (event.target === cy) {
        handlers_ref.current.on_clear_selection();
      }
    });

    cy_ref.current = cy;

    return () => {
      cy.destroy();
      cy_ref.current = null;
    };
  }, [resolved_theme]);

  useEffect(() => {
    const cy = cy_ref.current;
    if (!cy) {
      return;
    }

    cy.style().fromJson(build_cytoscape_styles(resolved_theme)).update();
  }, [resolved_theme]);

  useEffect(() => {
    const cy = cy_ref.current;
    if (!cy) {
      return;
    }

    cy.elements().remove();
    cy.add(to_cytoscape_elements(nodes, edges));

    // 使用力导向布局，保证导入后的关系网络能在小规模语料中快速铺开。
    cy.layout({
      name: 'cose',
      animate: false,
      padding: 24,
      fit: true,
      randomize: false,
      nodeRepulsion: 280000,
      idealEdgeLength: 140,
      edgeElasticity: 120,
    }).run();
  }, [edges, nodes]);

  useEffect(() => {
    const cy = cy_ref.current;
    if (!cy) {
      return;
    }

    const highlighted_nodes: Set<string> = new Set(highlighted_node_ids);
    const highlighted_edges: Set<string> = new Set(highlighted_edge_ids);

    cy.elements().removeClass('highlighted muted selected');
    if (highlighted_nodes.size || highlighted_edges.size) {
      cy.elements().addClass('muted');
      highlighted_nodes.forEach((node_id) => {
        cy.getElementById(node_id).removeClass('muted').addClass('highlighted');
      });
      highlighted_edges.forEach((edge_id) => {
        cy.getElementById(edge_id).removeClass('muted').addClass('highlighted');
      });

      const highlighted_collection = cy.elements('.highlighted');
      if (highlighted_collection.length) {
        cy.animate({
          fit: {
            eles: highlighted_collection,
            padding: 72,
          },
          duration: 260,
        });
      }
    }

    if (selected_node_id) {
      const selected_node = cy.getElementById(selected_node_id);
      selected_node.addClass('selected');
      if (!highlighted_nodes.size && selected_node.length) {
        cy.animate({
          fit: {
            eles: selected_node.closedNeighborhood(),
            padding: 96,
          },
          duration: 220,
        });
      }
    }

    if (selected_edge_id) {
      const selected_edge = cy.getElementById(selected_edge_id);
      selected_edge.addClass('selected');
      if (!highlighted_nodes.size && !highlighted_edges.size && selected_edge.length) {
        cy.animate({
          fit: {
            eles: selected_edge.connectedNodes().union(selected_edge),
            padding: 96,
          },
          duration: 220,
        });
      }
    }
  }, [highlighted_edge_ids, highlighted_node_ids, selected_edge_id, selected_node_id]);

  return <div className='graph-canvas' ref={container_ref} />;
}
