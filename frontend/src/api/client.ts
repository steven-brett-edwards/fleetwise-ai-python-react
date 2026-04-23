// Centralized API base. Falls back to same-origin /api so prod (StaticFiles
// mount on FastAPI) just works. Override with VITE_API_BASE_URL in dev or for
// a split-deploy scenario.
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  readonly status: number
  readonly body: string
  constructor(status: number, body: string) {
    super(`API ${status}: ${body}`)
    this.status = status
    this.body = body
  }
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new ApiError(res.status, body)
  }
  return res
}

export async function apiGet<T>(path: string, parser: (raw: unknown) => T): Promise<T> {
  const res = await apiFetch(path)
  const raw = await res.json()
  return parser(raw)
}
