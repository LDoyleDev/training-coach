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

export type SignIns = Schemas['SignIns']
export type PasskeyView = Schemas['PasskeyView']
export type DeviceView = Schemas['DeviceView']

/** The signed-in person's passkeys and browsers; null when not signed in. */
export async function fetchSignIns(signal?: AbortSignal): Promise<SignIns | null> {
  const res = await fetch('/api/account/sign-ins', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as SignIns
}

async function remove(path: string): Promise<void> {
  const res = await fetch(path, { method: 'DELETE', credentials: 'same-origin' })
  if (res.status !== 204 && res.status !== 404)
    throw new Error(`The server answered ${res.status}.`)
}

export const removePasskey = (id: number) => remove(`/api/account/passkeys/${id}`)
export const signOutDevice = (id: number) => remove(`/api/account/devices/${id}`)

export async function signOut(): Promise<void> {
  await fetch('/api/auth/signout', { method: 'POST', credentials: 'same-origin' })
}

// ---------------------------------------------------------------- the guided session (#117)

export type TodayView = Schemas['TodayView']
export type Guided = Schemas['GuidedView']
export type GuidedItem = Schemas['ItemView']
export type GuidedSet = Schemas['SetView']
export type Done = Schemas['DoneView']
export type Kept = Schemas['ProgressView']
export type Saved = Schemas['SavedView']
export type Pending = Schemas['PendingView']
export type Routine = Schemas['RoutineView']
export type KeepBody = Schemas['KeepBody']

const json = { 'Content-Type': 'application/json' }

/** Today's guided session; null when not signed in. */
export async function fetchToday(signal?: AbortSignal): Promise<TodayView | null> {
  const res = await fetch('/api/session/today', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as TodayView
}

/** Keep where the person is. 'stale': another device moved on (reload). */
export async function keepProgress(body: KeepBody): Promise<number | 'stale'> {
  const res = await fetch('/api/session/progress', {
    method: 'PUT',
    headers: json,
    body: JSON.stringify(body),
    credentials: 'same-origin',
  })
  if (res.status === 409) return 'stale'
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return ((await res.json()) as { revision: number }).revision
}

/** Save the session as a workout: today's, or an earlier day's. 'stale': today changed. */
export async function saveSession(day?: string): Promise<Saved | 'stale'> {
  const res = await fetch('/api/session/save', {
    method: 'POST',
    headers: json,
    body: JSON.stringify(day ? { day } : {}),
    credentials: 'same-origin',
  })
  if (res.status === 409) return 'stale'
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Saved
}

/** Earlier days' guided sessions never saved. */
export async function fetchPending(signal?: AbortSignal): Promise<Pending[]> {
  const res = await fetch('/api/session/pending', { signal, credentials: 'same-origin' })
  if (!res.ok) return []
  return (await res.json()) as Pending[]
}

/** The stretches after a saved resistance workout, filling `minutes`; null when not offered. */
export async function fetchStretching(workoutId: number, minutes: number): Promise<Routine | null> {
  const res = await fetch(`/api/session/stretching/${workoutId}?minutes=${minutes}`, {
    credentials: 'same-origin',
  })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Routine
}

/** Log the stretching minutes on the workout: false when it already had its stretching. */
export async function logStretching(workoutId: number, minutes: number): Promise<boolean> {
  const res = await fetch(`/api/session/stretching/${workoutId}`, {
    method: 'POST',
    headers: json,
    body: JSON.stringify({ minutes }),
    credentials: 'same-origin',
  })
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return ((await res.json()) as Schemas['StretchedView']).logged
}

// ---------------------------------------------------------------- baseline tests (#94)

export type FitnessTest = Schemas['TestView']
export type TestDay = Schemas['TestDayView']
export type TestDayBody = Schemas['TestDayBody']
export type TestResult = Schemas['TestResultView']

/** Every test and every saved test day; null when not signed in. */
export async function fetchTests(
  signal?: AbortSignal,
): Promise<{ tests: FitnessTest[]; days: TestDay[] } | null> {
  const [tests, days] = await Promise.all([
    fetch('/api/tests', { signal, credentials: 'same-origin' }),
    fetch('/api/tests/results', { signal, credentials: 'same-origin' }),
  ])
  if (tests.status === 401 || days.status === 401) return null
  if (!tests.ok || !days.ok) throw new Error('The server answered with an error.')
  return { tests: (await tests.json()) as FitnessTest[], days: (await days.json()) as TestDay[] }
}

/** Save a test day: its id, or a string saying why the server refused it. */
export async function saveTestDay(body: TestDayBody): Promise<number | string> {
  const res = await fetch('/api/tests', {
    method: 'POST',
    headers: json,
    body: JSON.stringify(body),
    credentials: 'same-origin',
  })
  if (res.status === 422) {
    const detail = ((await res.json()) as { detail?: unknown }).detail
    return typeof detail === 'string' ? detail : 'Those results could not be saved.'
  }
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return ((await res.json()) as Schemas['TestDaySaved']).id
}

// ---------------------------------------------------------------- body measurements (#142)

export type MeasureKind = Schemas['KindView']
export type Measurement = Schemas['MeasurementView']
export type MeasureBody = Schemas['MeasureBody']

/** The kinds and every measurement; null when not signed in. */
export async function fetchBody(
  signal?: AbortSignal,
): Promise<{ kinds: MeasureKind[]; entries: Measurement[] } | null> {
  const [kinds, entries] = await Promise.all(
    ['/api/body/kinds', '/api/body'].map((path) =>
      fetch(path, { signal, credentials: 'same-origin' }),
    ),
  )
  if (kinds.status === 401 || entries.status === 401) return null
  if (!kinds.ok || !entries.ok) throw new Error('The server answered with an error.')
  return {
    kinds: (await kinds.json()) as MeasureKind[],
    entries: (await entries.json()) as Measurement[],
  }
}

/** Save a day's measurements: true, or why the server refused them. */
export async function saveBody(body: MeasureBody): Promise<true | string> {
  const res = await fetch('/api/body', {
    method: 'PUT',
    headers: json,
    body: JSON.stringify(body),
    credentials: 'same-origin',
  })
  if (res.status === 422) {
    const detail = ((await res.json()) as { detail?: unknown }).detail
    return typeof detail === 'string' ? detail : 'Those values could not be saved.'
  }
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return true
}

export const deleteMeasurement = (on: string, kind: string) => remove(`/api/body/${on}/${kind}`)
