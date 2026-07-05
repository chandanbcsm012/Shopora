import type { ErrorEnvelope } from './types'

const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

/** Typed error thrown for every non-2xx response, per the CONTRACTS.md error envelope. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: Record<string, unknown>

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

type TokenGetter = () => string | null
/** Called on a 401; should attempt a refresh and return the new access token, or null if refresh failed. */
type UnauthorizedHandler = () => Promise<string | null>

let getAccessToken: TokenGetter = () => null
let onUnauthorized: UnauthorizedHandler | null = null

/** Wired up by AuthContext so the client can attach tokens and retry on expiry. */
export function configureApiClient(options: {
  getAccessToken?: TokenGetter
  onUnauthorized?: UnauthorizedHandler | null
}): void {
  if (options.getAccessToken) getAccessToken = options.getAccessToken
  if (options.onUnauthorized !== undefined) onUnauthorized = options.onUnauthorized
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined | null>
  /** Skip attaching the Authorization header (register/login/refresh). */
  skipAuth?: boolean
  /** Internal flag to prevent infinite refresh loops. */
  isRetry?: boolean
}

/**
 * Exposes the currently-configured Bearer token to callers that need to
 * build their own `fetch` request outside `apiRequest<T>` (currently just
 * the invoice download, which returns raw PDF bytes rather than JSON).
 */
export function getAuthToken(): string | null {
  return getAccessToken()
}

export function buildUrl(path: string, query?: RequestOptions['query']): string {
  const base = API_BASE_URL.replace(/\/+$/, '')
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  const url = new URL(base + cleanPath)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value))
      }
    }
  }
  return url.toString()
}

/**
 * Core fetch wrapper. Adds the Bearer token, serializes JSON bodies, parses
 * the `{items,total,page,page_size}` pagination envelope generically (the
 * caller just types the response as `PaginatedResponse<T>`), and on non-2xx
 * responses parses the `{error:{code,message,details}}` envelope and throws
 * an `ApiError`. On a 401 it will attempt one token refresh + retry via the
 * `onUnauthorized` hook configured by AuthContext.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, skipAuth = false, isRetry = false } = options

  // FormData bodies (e.g. the media upload endpoint) must NOT get a
  // `Content-Type: application/json` header or a JSON.stringify()'d body —
  // the browser sets the multipart boundary itself when it sees a FormData
  // body, and stringifying it would just produce "[object FormData]".
  const isFormData = body instanceof FormData

  const headers: Record<string, string> = {}
  if (body !== undefined && !isFormData) headers['Content-Type'] = 'application/json'
  if (!skipAuth) {
    const token = getAccessToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
  })

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    if (response.status === 401 && !skipAuth && !isRetry && onUnauthorized) {
      const newToken = await onUnauthorized()
      if (newToken) {
        return apiRequest<T>(path, { ...options, isRetry: true })
      }
    }

    const envelope = payload as ErrorEnvelope | null
    if (envelope && envelope.error) {
      throw new ApiError(response.status, envelope.error.code, envelope.error.message, envelope.error.details)
    }
    throw new ApiError(response.status, 'INTERNAL_ERROR', response.statusText || 'Request failed')
  }

  return payload as T
}
