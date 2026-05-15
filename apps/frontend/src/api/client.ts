/**
 * Custom fetch instance consumed by orval-generated API clients.
 *
 * Auth: httpOnly cookies set by the backend (not localStorage).
 * Errors: backend returns RFC 9457 Problem Details on failure.
 */

const BASE_URL = import.meta.env['VITE_API_URL'] ?? ''

export interface RequestConfig {
  url: string
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  params?: Record<string, unknown>
  data?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal
}

export async function customInstance<T>(config: RequestConfig): Promise<T> {
  const url = new URL(`${BASE_URL}${config.url}`, window.location.origin)

  if (config.params) {
    for (const [key, value] of Object.entries(config.params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value))
      }
    }
  }

  const response = await fetch(url.toString(), {
    method: config.method,
    headers: {
      'Content-Type': 'application/json',
      ...config.headers,
    },
    credentials: 'include', // sends httpOnly auth cookies
    body: config.data !== undefined ? JSON.stringify(config.data) : undefined,
    signal: config.signal,
  })

  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as Record<string, unknown>
    throw new ApiError(response.status, problem)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

/** RFC 9457 Problem Details error */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem: Record<string, unknown>
  ) {
    const detail = typeof problem['detail'] === 'string' ? problem['detail'] : `HTTP ${status}`
    super(detail)
    this.name = 'ApiError'
  }
}
