import { confirmWithPasskey, SignedOutError, signInWithPasskey } from './index'
import type { components } from './schema'

// Connecting an AI app (ADR-0047 C). Types come from the backend's schema (ADR-0020).
type Schemas = components['schemas']
export type ConsentView = Schemas['ConsentView']
export type ConsentScope = Schemas['ConsentScopeView']
type GoTo = Schemas['GoTo']

const post = (path: string, body: unknown) =>
  fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'same-origin',
  })

/** What a consent page asks for; null when the request has expired or was used. */
export async function fetchConsent(handle: string): Promise<ConsentView | null> {
  const res = await post('/api/connect/details', { handle })
  if (res.status === 404 || res.status === 422) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as ConsentView
}

/**
 * Prove it's you with your passkey on this page: confirm with the fingerprint when signed in,
 * otherwise sign in with it. A link from the bot isn't enough to connect an AI app. False when
 * there's no passkey or it wasn't accepted.
 */
async function provePasskey(): Promise<boolean> {
  try {
    return await confirmWithPasskey()
  } catch (error) {
    if (!(error instanceof SignedOutError)) throw error
  }
  return signInWithPasskey()
}

/** Where to go next, or what went wrong: 'passkey', 'expired' or the server's reason. */
export type Approval = GoTo | { problem: string }

/** Passkey, then bind this page to this browser, then approve with the ticked scopes. */
export async function approveConsent(
  consent: ConsentView,
  handle: string,
  scopes: string[],
): Promise<Approval> {
  if (!(await provePasskey())) return { problem: 'passkey' }
  const bound = await post('/api/connect/bind', { handle })
  if (bound.status === 409) return { problem: 'expired' }
  if (bound.status !== 204) return { problem: 'passkey' }
  const res = await post('/api/connect/approve', {
    handle,
    client_id: consent.client_id,
    redirect_uri: consent.redirect_uri,
    scopes,
  })
  if (res.status === 400) {
    const body = (await res.json()) as { detail?: string }
    return { problem: body.detail ?? 'expired' }
  }
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as GoTo
}

export type Connection = Schemas['ConnectionView']

/** The AI apps I've connected; null when not signed in. */
export async function fetchConnections(signal?: AbortSignal): Promise<Connection[] | null> {
  const res = await fetch('/api/account/connections', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Connection[]
}

/** Revoke a connected app: it can't read anything from now on. */
export async function revokeConnection(id: number): Promise<void> {
  const res = await fetch(`/api/account/connections/${id}`, {
    method: 'DELETE',
    credentials: 'same-origin',
  })
  if (res.status !== 204 && res.status !== 404)
    throw new Error(`The server answered ${res.status}.`)
}

/** Don't allow: where to send the person back; null when the request has already gone. */
export async function denyConsent(handle: string): Promise<string | null> {
  const res = await post('/api/connect/deny', { handle })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return ((await res.json()) as GoTo).redirect
}
