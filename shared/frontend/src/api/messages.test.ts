import { describe, expect, it } from 'vitest'
import { ApiError } from './client'
import { FALLBACK_MESSAGE, makeMessageFor } from './messages'

const messageFor = makeMessageFor({
  member_in_use: 'Membro in uso.',
  'invalid_input:name': 'Il nome è obbligatorio.',
})

function apiError(code: string, field: string | null = null) {
  return new ApiError(400, code, field, 'english detail', null)
}

describe('makeMessageFor', () => {
  it('prefers the code:field message', () => {
    expect(messageFor(apiError('invalid_input', 'name'))).toBe('Il nome è obbligatorio.')
  })

  it('falls back to the code message when the field has none', () => {
    expect(messageFor(apiError('invalid_input', 'color'))).toBe('Dati non validi.')
  })

  it('uses the app table for app-specific codes', () => {
    expect(messageFor(apiError('member_in_use'))).toBe('Membro in uso.')
  })

  it('lets the app override a common message', () => {
    const custom = makeMessageFor({ not_found: 'Sparito!' })

    expect(custom(apiError('not_found'))).toBe('Sparito!')
  })

  it.each([
    ['an unknown code', apiError('http_413')],
    ['a plain Error', new Error('boom')],
    ['a non-error value', 'boom'],
  ])('uses the fallback for %s', (_label, error) => {
    expect(messageFor(error)).toBe(FALLBACK_MESSAGE)
  })

  it('never shows the backend English message', () => {
    expect(messageFor(apiError('member_in_use'))).not.toContain('english')
  })
})
