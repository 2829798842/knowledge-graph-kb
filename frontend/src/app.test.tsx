import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from './app';

const fetch_mock = vi.fn(async (input: RequestInfo | URL) => {
  const url = input.toString();

  if (url.includes('/api/kb/imports/jobs')) {
    return new Response(JSON.stringify([]), { status: 200 });
  }
  if (url.includes('/api/kb/graph/manual-relations')) {
    return new Response(JSON.stringify([]), { status: 200 });
  }
  if (url.includes('/api/kb/graph')) {
    return new Response(JSON.stringify({ nodes: [], edges: [] }), { status: 200 });
  }
  if (url.includes('/api/kb/chat/sessions')) {
    return new Response(JSON.stringify([]), { status: 200 });
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

  it('renders the workspace shell and requests the core APIs', async () => {
    render(<App />);

    expect(screen.getAllByText('知识问答').length).toBeGreaterThan(0);
    expect(screen.getAllByText('知识图谱').length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(fetch_mock.mock.calls.length).toBeGreaterThanOrEqual(4);
    });

    expect(
      fetch_mock.mock.calls.some(([request]) =>
        request.toString().includes('/api/kb/imports/jobs'),
      ),
    ).toBe(true);
    expect(
      fetch_mock.mock.calls.some(([request]) => request.toString().includes('/api/kb/sources')),
    ).toBe(true);
    expect(
      fetch_mock.mock.calls.some(([request]) => request.toString().includes('/api/kb/graph')),
    ).toBe(true);
    expect(
      fetch_mock.mock.calls.some(([request]) =>
        request.toString().includes('/api/kb/graph/manual-relations'),
      ),
    ).toBe(true);
    expect(
      fetch_mock.mock.calls.some(([request]) =>
        request.toString().includes('/api/kb/chat/sessions'),
      ),
    ).toBe(true);
  });
});
