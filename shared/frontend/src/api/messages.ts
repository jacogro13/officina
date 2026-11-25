// canonical: frontend/src/api/messages.ts v1
// Error code → Italian text (Blueprint v2, D2 + F3). The only place this happens.
//
// Each app writes a small `api/errors.ts`:
//
//   export const messageFor = makeMessageFor({
//     member_in_use: 'Impossibile eliminare: il membro è usato in una o più attività.',
//     'invalid_input:name': 'Il nome è obbligatorio.',
//   })
//
// Lookup order: `code:field`, then `code`, then the common table, then the fallback.

import { ApiError } from './client'

export type MessageTable = Record<string, string>

export const COMMON_MESSAGES: MessageTable = {
  network_error: 'Server non raggiungibile. Controlla la connessione e riprova.',
  internal_error: 'Errore del server. Riprova tra poco.',
  not_found: 'Elemento non trovato: forse è stato eliminato. Ricarica la pagina.',
  conflict: 'Operazione non possibile nello stato attuale.',
  invalid_input: 'Dati non validi.',
}

export const FALLBACK_MESSAGE = 'Errore imprevisto. Riprova.'

export function makeMessageFor(appMessages: MessageTable): (error: unknown) => string {
  const table: MessageTable = { ...COMMON_MESSAGES, ...appMessages }
  return (error: unknown): string => {
    if (!(error instanceof ApiError)) return FALLBACK_MESSAGE
    const byField = error.field ? table[`${error.code}:${error.field}`] : undefined
    return byField ?? table[error.code] ?? FALLBACK_MESSAGE
  }
}
