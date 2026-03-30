/**
 * Shared HTTP helpers for the knowledge-base frontend.
 */

export class ApiRequestError extends Error {
  code: string;
  status: number;

  constructor(message: string, options: { code: string; status: number }) {
    super(message);
    this.name = 'ApiRequestError';
    this.code = options.code;
    this.status = options.status;
  }
}

export function build_query_string(
  params: Record<string, string | number | boolean | string[] | undefined>,
): string {
  const search_params = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined) {
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((item) => search_params.append(key, item));
      return;
    }
    search_params.set(key, String(value));
  });
  const query_string: string = search_params.toString();
  return query_string ? `?${query_string}` : '';
}

export async function request_json<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    throw await build_request_error(response);
  }
  return (await response.json()) as T;
}

async function build_request_error(response: Response): Promise<ApiRequestError> {
  const content_type: string = response.headers.get('content-type') ?? '';

  if (content_type.includes('application/json')) {
    const payload = (await response.json().catch(() => null)) as
      | { code?: string; message?: string; detail?: string | { code?: string; message?: string } }
      | null;

    const nested_detail =
      payload?.detail && typeof payload.detail === 'object' && !Array.isArray(payload.detail)
        ? payload.detail
        : null;
    const message =
      payload?.message ||
      (typeof payload?.detail === 'string' ? payload.detail : undefined) ||
      nested_detail?.message ||
      `请求失败 (${response.status})`;
    const code = payload?.code || nested_detail?.code || `http_${response.status}`;
    return new ApiRequestError(message, { code, status: response.status });
  }

  const text = (await response.text()).trim();
  return new ApiRequestError(text || `请求失败 (${response.status})`, {
    code: `http_${response.status}`,
    status: response.status,
  });
}
