import {
  browserSupportsWebAuthn,
  startAuthentication,
  startRegistration,
} from '@simplewebauthn/browser'
import type { components } from './schema'

// API types come from the backend's OpenAPI schema (ADR-0020); never redeclare them here.
type Schemas = components['schemas']
export type ExerciseKind = Schemas['ExerciseKind']
export type SessionType = Schemas['SessionView']['type']
export type Exercise = Schemas['ExerciseView']
export type Session = Schemas['SessionView']
export type Plan = Schemas['PlanView']

export async function fetchPlan(signal?: AbortSignal): Promise<Plan> {
  const res = await fetch('/api/plan', { signal })
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Plan
}

const range = (a: number, b: number) => (a === b ? `${a}` : `${a}–${b}`)

/** "4 × 8–15 per side", "1 × 45–75 min", "2 × 30–60 s" */
export function prescription(e: Exercise): string {
  const unit = e.kind === 'duration_min' ? ' min' : e.kind === 'seconds' ? ' s' : ''
  const side = e.per_side ? ' per side' : ''
  const body = `${range(e.rep_min, e.rep_max)}${unit}${side}`
  return e.sets === 1 ? body : `${e.sets} × ${body}`
}

/** Short headline figure for a session: sets for strength work, minutes for cardio. */
export function sessionSize(s: Session): string {
  const timed = s.exercises.find((e) => e.kind === 'duration_min')
  if (s.type === 'conditioning' && timed) return `${range(timed.rep_min, timed.rep_max)} min`
  if (s.type === 'conditioning') return `${s.exercises[0]?.rep_min ?? 0}+ rounds`
  return `${s.total_sets} sets`
}

/** Exchange a one-time sign-in link for a session cookie (ADR-0036). False when refused. */
export async function redeemLink(token: string): Promise<boolean> {
  const res = await fetch('/api/auth/redeem', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
    credentials: 'same-origin',
  })
  if (res.status === 204) return true
  if (res.status === 401 || res.status === 422) return false
  throw new Error(`The server answered ${res.status}.`)
}

/** Whether this browser can use passkeys (fingerprint or face sign-in). */
export function passkeysSupported(): boolean {
  return browserSupportsWebAuthn()
}

async function ceremonyOptions(path: string) {
  const res = await fetch(path, { method: 'POST', credentials: 'same-origin' })
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return res.json()
}

async function answer(path: string, credential: unknown): Promise<boolean> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
    credentials: 'same-origin',
  })
  if (res.status === 204) return true
  if (res.status === 400 || res.status === 401) return false
  throw new Error(`The server answered ${res.status}.`)
}

/** Add a passkey for the signed-in person (ADR-0036). Throws if the user cancels. */
export async function addPasskey(): Promise<boolean> {
  const optionsJSON = await ceremonyOptions('/api/auth/passkeys/register/options')
  const credential = await startRegistration({ optionsJSON })
  return answer('/api/auth/passkeys/register', credential)
}

/** Sign in with a passkey on this device (ADR-0036). Throws if the user cancels. */
export async function signInWithPasskey(): Promise<boolean> {
  const optionsJSON = await ceremonyOptions('/api/auth/passkeys/sign-in/options')
  const credential = await startAuthentication({ optionsJSON })
  return answer('/api/auth/passkeys/sign-in', credential)
}
