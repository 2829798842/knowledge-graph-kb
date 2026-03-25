/**
 * Shared HTTP helpers for the knowledge-base frontend.
 */

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
    const content_type: string = response.headers.get('content-type') ?? '';
    if (content_type.includes('application/json')) {
      const payload = (await response.json().catch(() => null)) as
        | { detail?: string; message?: string }
        | null;
      throw new Error(payload?.detail || payload?.message || `璇锋眰澶辫触 (${response.status})`);
    }
    const text = (await response.text()).trim();
    throw new Error(text || `璇锋眰澶辫触 (${response.status})`);
  }
  return (await response.json()) as T;
}
