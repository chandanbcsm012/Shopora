import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiRequest, configureApiClient } from './client'

function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'status text',
    text: async () => (body === null ? '' : JSON.stringify(body)),
  } as unknown as Response
}

describe('apiRequest', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    configureApiClient({ getAccessToken: () => null, onUnauthorized: null })
  })

  it('resolves with the parsed JSON body on a 2xx response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse(200, { id: '1', name: 'Widget' })))

    const result = await apiRequest<{ id: string; name: string }>('/products/1')

    expect(result).toEqual({ id: '1', name: 'Widget' })
  })

  it('parses the {error:{code,message,details}} envelope into a typed ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        mockResponse(404, {
          error: { code: 'RESOURCE_NOT_FOUND', message: 'Product not found', details: { id: 'abc' } },
        }),
      ),
    )

    await expect(apiRequest('/products/abc')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      code: 'RESOURCE_NOT_FOUND',
      message: 'Product not found',
      details: { id: 'abc' },
    })
  })

  it('falls back to a generic ApiError when the body has no error envelope', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse(500, {})))

    await expect(apiRequest('/boom')).rejects.toBeInstanceOf(ApiError)
  })

  it('treats a 204 response as a successful empty result', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse(204, null)))

    await expect(apiRequest('/auth/logout', { method: 'POST' })).resolves.toBeUndefined()
  })

  it('attaches the Authorization header when a token is configured', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)
    configureApiClient({ getAccessToken: () => 'my-token' })

    await apiRequest('/auth/me')

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer my-token')
  })

  it('retries once via onUnauthorized after a 401 and returns the retried result', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse(401, { error: { code: 'NOT_AUTHENTICATED', message: 'expired' } }))
      .mockResolvedValueOnce(mockResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    const onUnauthorized = vi.fn().mockResolvedValue('fresh-token')
    configureApiClient({ getAccessToken: () => 'stale-token', onUnauthorized })

    const result = await apiRequest<{ ok: boolean }>('/auth/me')

    expect(result).toEqual({ ok: true })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
