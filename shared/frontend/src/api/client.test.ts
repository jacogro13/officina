import { describe, expect, it } from 'vitest'
import { ApiError, createApiClient } from './client'

/** A hand-written fake `fetch` that answers every request with one canned response. */
function fakeFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const calls: Request[] = []
  const fetch = async (request: Request) => {
    calls.push(request)
    const text = typeof body === 'string' ? body : JSON.stringify(body)
    return new Response(status === 204 ? null : text, {
      status,
      headers: { 'Content-Type': typeof body === 'string' ? 'text/html' : 'application/json', ...headers },
    })
  }
  return { fetch, calls }
}

function failingFetch() {
  return async () => {
    throw new TypeError('Failed to fetch')
  }
}

async function caught(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    if (error instanceof ApiError) return error
    throw error
  }
  throw new Error('expected the request to fail')
}

describe('createApiClient', () => {
  it('returns typed data on success', async () => {
    const { fetch } = fakeFetch(200, [{ member_id: '1', name: 'Anna' }])
    const api = createApiClient({ baseUrl: 'http://test/api', fetch })

    const { data } = await api.GET('/members')

    expect(data).toEqual([{ member_id: '1', name: 'Anna' }])
  })

  it('turns an error response into an ApiError with code, field and request id', async () => {
    const { fetch } = fakeFetch(
      422,
      { code: 'invalid_input', message: 'Member.name: too short', field: 'name' },
      { 'X-Request-ID': 'req42' },
    )
    const api = createApiClient({ baseUrl: 'http://test/api', fetch })

    const error = await caught(api.POST('/members', { body: { name: '' } }))

    expect(error.status).toBe(422)
    expect(error.code).toBe('invalid_input')
    expect(error.field).toBe('name')
    expect(error.requestId).toBe('req42')
  })

  it.each([
    [502, 'internal_error'],
    [404, 'unknown'],
  ])('handles a non-JSON %i response', async (status, code) => {
    const { fetch } = fakeFetch(status, '<html>Bad Gateway</html>')
    const api = createApiClient({ baseUrl: 'http://test/api', fetch })

    const error = await caught(api.GET('/members'))

    expect(error.status).toBe(status)
    expect(error.code).toBe(code)
  })

  it('turns a network failure into a network_error ApiError', async () => {
    const api = createApiClient({ baseUrl: 'http://test/api', fetch: failingFetch() })

    const error = await caught(api.GET('/members'))

    expect(error.status).toBe(0)
    expect(error.code).toBe('network_error')
  })
})
