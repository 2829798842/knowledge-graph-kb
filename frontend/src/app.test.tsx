/**
 * Verify the app entry renders the workspace shell and hits the core APIs.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./features/knowledge_base/graph_browser/components/knowledge_graph_canvas', () => ({
  KnowledgeGraphCanvas: () => <div data-testid='graph-canvas'>graph canvas</div>,
}));

import App from './app';

const fetch_mock = vi.fn(async (input: RequestInfo | URL) => {
  const url: string = input.toString();
  if (url.includes('/api/kb/imports/jobs')) {
    return new Response(JSON.stringify([]), { status: 200 });
  }
  if (url.includes('/api/kb/graph/manual-relations')) {
    return new Response(JSON.stringify([]), { status: 200 });
  }
  if (url.includes('/api/kb/graph')) {
    return new Response(JSON.stringify({ nodes: [], edges: [] }), { status: 200 });
  }
  if (url.includes('/api/kb/sources')) {
    return new Response(JSON.stringify([]), { status: 200 });
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

  it('renders the knowledge-base workspace and requests the core APIs', async () => {
    render(<App />);

    expect(screen.getByText('\u77e5\u8bc6\u5e93\u5de5\u4f5c\u53f0')).toBeTruthy();
    expect(screen.getAllByText('\u5bfc\u5165\u4e2d\u5fc3').length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(fetch_mock.mock.calls.length).toBeGreaterThanOrEqual(4);
    });

    expect(fetch_mock.mock.calls.some(([request]) => request.toString().includes('/api/kb/imports/jobs'))).toBe(true);
    expect(fetch_mock.mock.calls.some(([request]) => request.toString().includes('/api/kb/sources'))).toBe(true);
    expect(fetch_mock.mock.calls.some(([request]) => request.toString().includes('/api/kb/graph'))).toBe(true);
    expect(
      fetch_mock.mock.calls.some(([request]) => request.toString().includes('/api/kb/graph/manual-relations')),
    ).toBe(true);
  });
});
