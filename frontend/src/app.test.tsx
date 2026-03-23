/**
 * 模块名称：app.test
 * 主要功能：验证知识库首页在基础数据加载场景下可以正常渲染。
 */

import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./features/knowledge_base/components/graph_canvas/graph_canvas', () => ({
  GraphCanvas: () => <div data-testid='graph-canvas'>图谱画布</div>,
}));

import App from './app';

const fetch_mock = vi.fn(async (input: RequestInfo | URL) => {
  const url: string = input.toString();
  if (url.includes('/api/documents')) {
    return new Response(JSON.stringify([]), { status: 200 });
  }
  if (url.includes('/api/graph')) {
    return new Response(JSON.stringify({ nodes: [], edges: [] }), { status: 200 });
  }
  return new Response(JSON.stringify({}), { status: 200 });
});

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetch_mock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetch_mock.mockClear();
    window.localStorage.clear();
  });

  it('renders the workspace shell', async () => {
    render(<App />);

    expect(screen.getByText('导入文档、查看连接，并直接向图谱提问。')).toBeInTheDocument();
    await waitFor(() => {
      expect(fetch_mock).toHaveBeenCalled();
    });
    expect(screen.getByText('导入文档')).toBeInTheDocument();
    expect(screen.getByText('知识图谱')).toBeInTheDocument();
  });
});
