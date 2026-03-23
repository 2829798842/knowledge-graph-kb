/**
 * 工作区外壳的基础渲染测试。
 */

import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./features/knowledge_base/components/graph_canvas', () => ({
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
  if (url.includes('/api/model-config')) {
    return new Response(
      JSON.stringify({
        provider: 'openai',
        base_url: 'https://api.openai.com/v1',
        llm_model: 'gpt-5.4-mini',
        embedding_model: 'text-embedding-3-large',
        has_api_key: true,
        api_key_preview: 'sk-t...1234',
        api_key_source: 'environment',
        reindex_required: false,
        notice: null,
      }),
      { status: 200 },
    );
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

  it('能够渲染工作区外壳和模型配置面板', async () => {
    render(<App />);

    expect(screen.getByText('导入文档、查看连接，并直接向知识图谱提问。')).toBeInTheDocument();
    await waitFor(() => {
      expect(fetch_mock).toHaveBeenCalled();
    });
    expect(screen.getByText('导入文档')).toBeInTheDocument();
    expect(screen.getByText('知识图谱')).toBeInTheDocument();
    expect(screen.getByText('模型配置')).toBeInTheDocument();
    expect(screen.getByText('保存模型配置')).toBeInTheDocument();
    expect(screen.getByText('测试连接')).toBeInTheDocument();
  });
});
