import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../testing/server'
import { ApiError, apiFetch, apiGet } from './client'

describe('apiFetch', () => {
  it('resolves for a 2xx response', async () => {
    server.use(http.get('/api/ping', () => HttpResponse.json({ ok: true })))

    const res = await apiFetch('/ping')

    expect(res.status).toBe(200)
  })

  it('throws ApiError carrying status and body for a non-2xx response', async () => {
    server.use(
      http.get('/api/ping', () => new HttpResponse('boom', { status: 503 })),
    )

    const err = await apiFetch('/ping').catch((e: unknown) => e)

    expect(err).toBeInstanceOf(ApiError)
    const apiError = err as ApiError
    expect(apiError.status).toBe(503)
    expect(apiError.body).toBe('boom')
    expect(apiError.message).toBe('API 503: boom')
  })

  it('sends JSON content type and merges caller headers', async () => {
    let seen: Headers | null = null
    server.use(
      http.get('/api/ping', ({ request }) => {
        seen = request.headers
        return HttpResponse.json({ ok: true })
      }),
    )

    await apiFetch('/ping', { headers: { 'X-Custom': 'yes' } })

    expect(seen!.get('content-type')).toBe('application/json')
    expect(seen!.get('x-custom')).toBe('yes')
  })
})

describe('apiGet', () => {
  it('parses the JSON body through the supplied parser', async () => {
    server.use(http.get('/api/ping', () => HttpResponse.json({ Value: 7 })))

    const parsed = await apiGet('/ping', (raw) => (raw as { Value: number }).Value * 2)

    expect(parsed).toBe(14)
  })

  it('propagates parser failures (contract drift surfaces loudly)', async () => {
    server.use(http.get('/api/ping', () => HttpResponse.json({ Wrong: 'shape' })))

    await expect(
      apiGet('/ping', () => {
        throw new Error('parse failed')
      }),
    ).rejects.toThrow('parse failed')
  })
})
