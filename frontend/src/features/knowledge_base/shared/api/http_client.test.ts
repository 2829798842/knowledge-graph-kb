import { describe, expect, it, vi } from 'vitest';

import { ApiRequestError, request_json } from './http_client';

describe('request_json', () => {
  it('parses nested JSON error payloads into ApiRequestError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: { code: 'graph_invalid', message: '图谱请求无效。' } }), {
          status: 400,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    );

    await expect(request_json('/api/test')).rejects.toEqual(
      expect.objectContaining({
        name: 'ApiRequestError',
        code: 'graph_invalid',
        message: '图谱请求无效。',
        status: 400,
      } satisfies Partial<ApiRequestError>),
    );
  });

  it('falls back to a readable Chinese message for non-JSON errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('', { status: 503, headers: { 'content-type': 'text/plain' } })),
    );

    await expect(request_json('/api/test')).rejects.toEqual(
      expect.objectContaining({
        code: 'http_503',
        message: '请求失败 (503)',
        status: 503,
      } satisfies Partial<ApiRequestError>),
    );
  });
});
