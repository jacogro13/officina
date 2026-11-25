// canonical: frontend/src/api/client.ts v1
// The one API client of every frontend (Blueprint v2, F1 + D2 + D6).
//
// `schema.d.ts` next to this file is generated from the backend (`make types`);
// it is the only thing that differs between apps, so this file is identical everywhere.
//
//   const { data } = await api.GET('/members')   // paths, params, bodies, responses all typed
//
// Every failure becomes an `ApiError` with a stable `code` — never a bare string —
// so components show `messageFor(error)` (messages.ts) instead of inspecting
// status codes or message text.

import createClient, { type ClientOptions, type Middleware } from 'openapi-fetch'
import type { paths } from './schema'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly field: string | null
  readonly requestId: string | null

  constructor(status: number, code: string, field: string | null, message: string, requestId: string | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.field = field
    this.requestId = requestId
  }
}

interface ErrorBody {
  code?: string
  message?: string
  field?: string | null
}

export const throwOnError: Middleware = {
  async onResponse({ response }) {
    if (response.ok) return undefined
    let body: ErrorBody = {}
    try {
      body = await response.clone().json()
    } catch {
      // Not JSON (e.g. nginx 502 page): keep the defaults below.
    }
    throw new ApiError(
      response.status,
      body.code ?? (response.status >= 500 ? 'internal_error' : 'unknown'),
      body.field ?? null,
      body.message ?? response.statusText,
      response.headers.get('X-Request-ID'),
    )
  },
  onError({ error }) {
    // fetch itself failed: server down, network gone, request aborted.
    if (error instanceof ApiError) return error
    return new ApiError(0, 'network_error', null, String(error), null)
  },
}

export function createApiClient(options: ClientOptions = {}) {
  const client = createClient<paths>({ baseUrl: '/api', ...options })
  client.use(throwOnError)
  return client
}

/** The app-wide client. Tests build their own with `createApiClient({ fetch })`. */
export const api = createApiClient()
