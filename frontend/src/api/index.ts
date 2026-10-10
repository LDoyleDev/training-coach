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

/** The training plan; null when not signed in (the site is private, ADR-0041). */
export async function fetchPlan(signal?: AbortSignal): Promise<Plan | null> {
  const res = await fetch('/api/plan', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
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

/** Changing passkeys needs a sign-in from the last few minutes (ADR-0040): a 403. */
export class StaleSignInError extends Error {
  constructor() {
    super('Sign in again to change passkeys.')
  }
}

/** Exchange a one-time sign-in link for a session cookie (ADR-0036). 'use-passkey' once a
 * passkey exists: then only the fingerprint signs in (ADR-0040). */
export async function redeemLink(token: string): Promise<'signed-in' | 'refused' | 'use-passkey'> {
  const res = await fetch('/api/auth/redeem', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
    credentials: 'same-origin',
  })
  if (res.status === 204) return 'signed-in'
  if (res.status === 403) return 'use-passkey'
  if (res.status === 401 || res.status === 422) return 'refused'
  throw new Error(`The server answered ${res.status}.`)
}

/** Whether this browser can use passkeys (fingerprint or face sign-in). */
export function passkeysSupported(): boolean {
  return browserSupportsWebAuthn()
}

async function ceremonyOptions(path: string) {
  const res = await fetch(path, { method: 'POST', credentials: 'same-origin' })
  if (res.status === 403) throw new StaleSignInError()
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
  if (res.status === 403) throw new StaleSignInError()
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

/** The sign-in ended while a page was open: a change answered 401. Pages say so and link to
 * sign in, keeping what was typed. */
export class SignedOutError extends Error {
  constructor() {
    super('Your sign-in has ended.')
  }
}

function signedIn(res: Response): Response {
  if (res.status === 401) throw new SignedOutError()
  return res
}

/** Today's guided session; null when not signed in. */
export async function fetchToday(signal?: AbortSignal): Promise<TodayView | null> {
  const res = await fetch('/api/session/today', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as TodayView
}

/** Keep where the person is. 'stale': another device moved on (reload). */
export async function keepProgress(body: KeepBody): Promise<number | 'stale'> {
  const res = signedIn(
    await fetch('/api/session/progress', {
      method: 'PUT',
      headers: json,
      body: JSON.stringify(body),
      credentials: 'same-origin',
    }),
  )
  if (res.status === 409) return 'stale'
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return ((await res.json()) as { revision: number }).revision
}

/** Save the session as a workout: today's, or an earlier day's. 'stale': today changed. */
export async function saveSession(day?: string): Promise<Saved | 'stale'> {
  const res = signedIn(
    await fetch('/api/session/save', {
      method: 'POST',
      headers: json,
      body: JSON.stringify(day ? { day } : {}),
      credentials: 'same-origin',
    }),
  )
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
  const res = signedIn(
    await fetch(`/api/session/stretching/${workoutId}?minutes=${minutes}`, {
      credentials: 'same-origin',
    }),
  )
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Routine
}

/** Log the stretching minutes on the workout: false when it already had its stretching. */
export async function logStretching(workoutId: number, minutes: number): Promise<boolean> {
  const res = signedIn(
    await fetch(`/api/session/stretching/${workoutId}`, {
      method: 'POST',
      headers: json,
      body: JSON.stringify({ minutes }),
      credentials: 'same-origin',
    }),
  )
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return ((await res.json()) as Schemas['StretchedView']).logged
}

// ---------------------------------------------------------------- baseline tests (#94)

export type FitnessTest = Schemas['TestView']
export type TestDay = Schemas['TestDayView']
export type TestDayBody = Schemas['TestDayBody']
export type TestResult = Schemas['TestResultView']
export type TestDayDue = Schemas['TestDayDueView']

/** Every test and every saved test day; null when not signed in. */
export async function fetchTests(
  signal?: AbortSignal,
): Promise<{ tests: FitnessTest[]; days: TestDay[]; due: TestDayDue | null } | null> {
  const [tests, days, due] = await Promise.all(
    ['/api/tests', '/api/tests/results', '/api/tests/due'].map((path) =>
      fetch(path, { signal, credentials: 'same-origin' }),
    ),
  )
  if ([tests, days, due].some((r) => r.status === 401)) return null
  if (![tests, days, due].every((r) => r.ok)) throw new Error('The server answered with an error.')
  return {
    tests: (await tests.json()) as FitnessTest[],
    days: (await days.json()) as TestDay[],
    due: (await due.json()) as TestDayDue | null,
  }
}

/** Save a test day: its id, or a string saying why the server refused it. */
export async function saveTestDay(body: TestDayBody): Promise<number | string> {
  const res = signedIn(
    await fetch('/api/tests', {
      method: 'POST',
      headers: json,
      body: JSON.stringify(body),
      credentials: 'same-origin',
    }),
  )
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
  const res = signedIn(
    await fetch('/api/body', {
      method: 'PUT',
      headers: json,
      body: JSON.stringify(body),
      credentials: 'same-origin',
    }),
  )
  if (res.status === 422) {
    const detail = ((await res.json()) as { detail?: unknown }).detail
    return typeof detail === 'string' ? detail : 'Those values could not be saved.'
  }
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return true
}

export async function deleteMeasurement(on: string, kind: string): Promise<void> {
  const res = signedIn(
    await fetch(`/api/body/${on}/${kind}`, { method: 'DELETE', credentials: 'same-origin' }),
  )
  if (res.status !== 204 && res.status !== 404)
    throw new Error(`The server answered ${res.status}.`)
}

// ---------------------------------------------------------------- progress photos (#143)

export type PhotoView = Schemas['PhotoView']
export type Pose = PhotoView['pose']

export async function fetchPhotos(signal?: AbortSignal): Promise<PhotoView[]> {
  const res = signedIn(await fetch('/api/photos', { signal, credentials: 'same-origin' }))
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as PhotoView[]
}

/** Upload a JPEG for a day and pose: true, or why the server refused it. */
export async function uploadPhoto(on: string, pose: Pose, jpeg: Blob): Promise<true | string> {
  const res = signedIn(
    await fetch(`/api/photos/${on}/${pose}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'image/jpeg' },
      body: jpeg,
      credentials: 'same-origin',
    }),
  )
  if (res.status === 413) return 'That photo is too large.'
  if (res.status === 415 || res.status === 422) {
    const detail = await res
      .json()
      .then((body: { detail?: unknown }) => body.detail)
      .catch(() => null) // a proxy's error page isn't JSON
    return typeof detail === 'string' ? detail : "That photo couldn't be stored."
  }
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return true
}

export async function deletePhoto(id: number): Promise<void> {
  const res = signedIn(
    await fetch(`/api/photos/${id}`, { method: 'DELETE', credentials: 'same-origin' }),
  )
  if (res.status !== 204 && res.status !== 404)
    throw new Error(`The server answered ${res.status}.`)
}

// ---------------------------------------------------------------- progress

export type Standing = Schemas['StandingView']

/** Each exercise's standing; null when not signed in. */
export async function fetchProgress(signal?: AbortSignal): Promise<Standing[] | null> {
  const res = await fetch('/api/progress', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Standing[]
}

// ---------------------------------------------------------------- your own AI (ADR-0047)

export type SummaryPeriod = '4w' | '12w' | 'all'

/** My training as Markdown for my own AI; health data only when asked for. */
export async function fetchAiSummary(
  period: SummaryPeriod,
  body: boolean,
  readiness: boolean,
): Promise<string> {
  const query = new URLSearchParams({ period, body: String(body), readiness: String(readiness) })
  const res = signedIn(
    await fetch(`/api/account/ai-summary?${query}`, { credentials: 'same-origin' }),
  )
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return res.text()
}

// ---------------------------------------------------------------- readiness (ADR-0046)

export type Readiness = Schemas['ReadinessView']
export type ReadinessStatus = Schemas['ReadinessSavedView']['status']

/** The readiness questions with my latest answers; null when not signed in. */
export async function fetchReadiness(signal?: AbortSignal): Promise<Readiness | null> {
  const res = await fetch('/api/readiness', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Readiness
}

/** Save a full set of answers; returns what they mean. */
export async function saveReadiness(answers: Record<string, boolean>): Promise<ReadinessStatus> {
  const res = signedIn(
    await fetch('/api/readiness', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers }),
    }),
  )
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return ((await res.json()) as Schemas['ReadinessSavedView']).status
}

/** Everything stored about me, as a zip (needs a recent sign-in, like a passkey change). */
export async function downloadExport(): Promise<Blob> {
  const res = await fetch('/api/account/export', { credentials: 'same-origin' })
  if (res.status === 403) throw new StaleSignInError()
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return res.blob()
}

/** Erase everything stored about me (ADR-0044); `confirm` is the word the person typed.
 *  Needs a recent sign-in; signs this browser out. */
export async function eraseAllMyData(confirm: string): Promise<void> {
  const res = signedIn(
    await fetch('/api/account/erase', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm }),
    }),
  )
  if (res.status === 403) throw new StaleSignInError()
  if (res.status !== 204) throw new Error(`The server answered ${res.status}.`)
}

// ---------------------------------------------------------------- my own AI key (ADR-0047 B)

export type AiStatus = Schemas['AiView']
export type AiOptions = Schemas['OptionsBody']
export type KeyCheck = 'works' | 'refused' | 'unreachable'

function checked(res: Response): KeyCheck | null {
  if (res.status === 400) return 'refused'
  if (res.status === 503) return 'unreachable'
  return null
}

/** Whether I have a key stored, its last four characters and my choices; null signed out. */
export async function fetchAiStatus(signal?: AbortSignal): Promise<AiStatus | null> {
  const res = await fetch('/api/account/ai', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as AiStatus
}

/** Check a Groq key with Groq and keep it encrypted. Needs a recent sign-in. */
export async function storeAiKey(key: string): Promise<AiStatus | KeyCheck> {
  const res = signedIn(
    await fetch('/api/account/ai/key', {
      method: 'PUT',
      headers: json,
      body: JSON.stringify({ key }),
      credentials: 'same-origin',
    }),
  )
  if (res.status === 403) throw new StaleSignInError()
  if (res.status === 422) return 'refused' // not shaped like a Groq key: never sent to Groq
  const problem = checked(res)
  if (problem) return problem
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as AiStatus
}

export async function setAiOptions(options: AiOptions): Promise<AiStatus> {
  const res = signedIn(
    await fetch('/api/account/ai', {
      method: 'PUT',
      headers: json,
      body: JSON.stringify(options),
      credentials: 'same-origin',
    }),
  )
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as AiStatus
}

export async function testAiKey(): Promise<KeyCheck> {
  const res = signedIn(
    await fetch('/api/account/ai/test', { method: 'POST', credentials: 'same-origin' }),
  )
  if (res.status === 204) return 'works'
  const problem = checked(res)
  if (problem) return problem
  throw new Error(`The server answered ${res.status}.`)
}

export async function removeAiKey(): Promise<void> {
  const res = signedIn(
    await fetch('/api/account/ai/key', { method: 'DELETE', credentials: 'same-origin' }),
  )
  if (res.status !== 204 && res.status !== 404)
    throw new Error(`The server answered ${res.status}.`)
}
