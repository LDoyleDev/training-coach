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

/** A change that needs a sign-in from the last few minutes (ADR-0040) answered 403, and the
 * person couldn't confirm with their fingerprint (cancelled, or no passkey here). */
export class StaleSignInError extends Error {
  constructor() {
    super('Confirm it’s you to do this.')
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

/** Confirm it's you with your fingerprint (ADR-0049): this browser then counts as freshly
 * signed in for 10 minutes. No new sign-in, no signing out. */
export async function confirmWithPasskey(): Promise<boolean> {
  const res = signedIn(
    await fetch('/api/auth/passkeys/confirm/options', {
      method: 'POST',
      credentials: 'same-origin',
    }),
  )
  if (res.status === 409) return false // no passkey to confirm with
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  const credential = await startAuthentication({ optionsJSON: await res.json() })
  const confirmed = signedIn(
    await fetch('/api/auth/passkeys/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
      credentials: 'same-origin',
    }),
  )
  if (confirmed.status === 400) return false // the fingerprint wasn't accepted
  if (confirmed.status !== 204) throw new Error(`The server answered ${confirmed.status}.`)
  return true
}

/**
 * Run a change that needs a recent sign-in. If the sign-in is too old, ask for the
 * fingerprint once (the phone shows its prompt) and try again, so nobody has to sign out and
 * in. Throws StaleSignInError when that isn't possible (cancelled, refused, no passkey).
 */
export async function withFreshSignIn<T>(change: () => Promise<T>): Promise<T> {
  try {
    return await change()
  } catch (error) {
    if (!(error instanceof StaleSignInError)) throw error
  }
  let confirmed = false
  try {
    confirmed = await confirmWithPasskey()
  } catch (error) {
    if (error instanceof SignedOutError) throw error
    // cancelled at the fingerprint prompt, or the browser refused: say what to do
  }
  if (!confirmed) throw new StaleSignInError()
  return change()
}

async function addPasskeyNow(): Promise<boolean> {
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

/** Add a passkey for the signed-in person (ADR-0036). Throws if the user cancels. */
export const addPasskey = () => withFreshSignIn(addPasskeyNow)
export const removePasskey = (id: number) =>
  withFreshSignIn(() => remove(`/api/account/passkeys/${id}`))
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

export type CardioOptions = Schemas['OptionsView']
export type CardioLog = Schemas['LogBody']
export type CardioLogged = Schemas['LoggedView']
export type CardioKind = CardioLog['kind']
export type CardioActivity = Schemas['CardioActivity']

/** Today's planned cardio, the activities and this week's minutes; null when signed out. */
export async function fetchCardio(signal?: AbortSignal): Promise<CardioOptions | null> {
  const res = await fetch('/api/cardio', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as CardioOptions
}

/** Log cardio in one step (ux-flow-plan A1). 'stale': today's session changed meanwhile. */
export async function logCardio(body: CardioLog): Promise<CardioLogged | 'stale'> {
  const res = signedIn(
    await fetch('/api/cardio', {
      method: 'POST',
      headers: json,
      body: JSON.stringify(body),
      credentials: 'same-origin',
    }),
  )
  if (res.status === 409) return 'stale'
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as CardioLogged
}

export type BandOffer = Schemas['BandOfferView']
export type BandCounted = Schemas['BandCounted']

/** Band workouts to count as cardio (ADR-0055); none when signed out. */
export async function fetchBandOffers(signal?: AbortSignal): Promise<BandOffer[]> {
  const res = await fetch('/api/band/offers', { signal, credentials: 'same-origin' })
  if (res.status === 401) return []
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as BandOffer[]
}

/** Count one. 'gone': no longer on offer; 'stale': today's session changed meanwhile. */
export async function countBandOffer(id: number): Promise<BandCounted | 'gone' | 'stale'> {
  const res = signedIn(
    await fetch(`/api/band/offers/${id}/count`, { method: 'POST', credentials: 'same-origin' }),
  )
  if (res.status === 404) return 'gone'
  if (res.status === 409) return 'stale'
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as BandCounted
}

export async function dismissBandOffer(id: number): Promise<void> {
  const res = signedIn(
    await fetch(`/api/band/offers/${id}/dismiss`, { method: 'POST', credentials: 'same-origin' }),
  )
  if (res.status !== 204 && res.status !== 404)
    throw new Error(`The server answered ${res.status}.`)
}

export type Changed = Schemas['ChangedView']
export type Choices = Schemas['ChoicesView']
export type Queued = Schemas['QueuedView']
export type UndoOffer = Schemas['UndoOfferView']
export type UndoState = Schemas['UndoView']
export type Undone = Schemas['UndoneView']
export type TodayChange = 'rest' | 'push' | 'next'

async function post(url: string, body: unknown): Promise<Response> {
  return signedIn(
    await fetch(url, {
      method: 'POST',
      headers: json,
      body: JSON.stringify(body),
      credentials: 'same-origin',
    }),
  )
}

/** Rest today, Push to tomorrow, or do the next session first (ux-flow-plan C2), for the
 * session the page shows. 'stale': today's session changed meanwhile. */
export async function changeToday(
  change: TodayChange,
  templateId: number,
): Promise<Changed | 'stale'> {
  const res = await post(`/api/today/${change}`, { template_id: templateId })
  if (res.status === 409) return 'stale'
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Changed
}

/** Do another session today instead of the one shown. 'stale': today changed meanwhile. */
export async function pickToday(templateId: number, pickedId: number): Promise<Changed | 'stale'> {
  const res = await post('/api/today/pick', { template_id: templateId, picked_id: pickedId })
  if (res.status === 409) return 'stale'
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Changed
}

/** What Swap offers today. 'stale': nothing planned today any more. */
export async function fetchChoices(): Promise<Choices | 'stale'> {
  const res = signedIn(await fetch('/api/today/choices', { credentials: 'same-origin' }))
  if (res.status === 409) return 'stale'
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Choices
}

/** What Undo would take back (ux-flow-plan C3), or why nothing can be. */
export async function fetchUndo(): Promise<UndoState> {
  const res = signedIn(await fetch('/api/today/undo', { credentials: 'same-origin' }))
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as UndoState
}

/** Undo the change the offer named (ADR-0048). A string: why it can't be undone now. */
export async function undoChange(eventId: number): Promise<Undone | string> {
  const res = await post('/api/today/undo', { event_id: eventId })
  if (res.status === 409) return ((await res.json()) as { detail: string }).detail
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Undone
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

// ---------------------------------------------------------------- home (B1)

export type Home = Schemas['HomeView']

/** What has been done, this week, the ladders and today's session; null when not signed in. */
export async function fetchHome(signal?: AbortSignal): Promise<Home | null> {
  const res = await fetch('/api/home', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Home
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

// ---------------------------------------------------------------- daily check (ADR-0053)

export type DailyCheck = Schemas['DailyCheckView']
export type DailyCheckAnswers = Schemas['CheckAnswers']

/** Today's daily check: the questions, and the answers with advice once given; null when not
 * signed in. */
export async function fetchDailyCheck(signal?: AbortSignal): Promise<DailyCheck | null> {
  const res = await fetch('/api/daily-check', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as DailyCheck
}

/** Answer today's check (again replaces); returns it with the advice. */
export async function saveDailyCheck(answers: DailyCheckAnswers): Promise<DailyCheck> {
  const res = signedIn(
    await fetch('/api/daily-check', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: json,
      body: JSON.stringify(answers),
    }),
  )
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as DailyCheck
}

// ---------------------------------------------------------------- weekly review (C4)

export type WeekReview = Schemas['ReviewWeekView']

/** The review of the week containing ``week`` (this week when absent); null when signed out. */
export async function fetchReview(week?: string, signal?: AbortSignal): Promise<WeekReview | null> {
  const query = week ? `?week=${encodeURIComponent(week)}` : ''
  const res = await fetch(`/api/review${query}`, { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as WeekReview
}

// ---------------------------------------------------------------- settings (ux-flow-plan C6)

export type MessageSettings = Schemas['SettingsView']
export type SettingsChange = Schemas['SettingsChange']

/** Message times, nudges, habits, protein, blocks and pause; null when not signed in. */
export async function fetchSettings(signal?: AbortSignal): Promise<MessageSettings | null> {
  const res = await fetch('/api/settings', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as MessageSettings
}

/** Change only what's given. 'invalid': the server refused a value (as the bot would). */
export async function saveSettings(change: SettingsChange): Promise<MessageSettings | 'invalid'> {
  const res = signedIn(
    await fetch('/api/settings', {
      method: 'PATCH',
      credentials: 'same-origin',
      headers: json,
      body: JSON.stringify(change),
    }),
  )
  if (res.status === 422) return 'invalid'
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as MessageSettings
}

// ---------------------------------------------------------------- habits (ux-flow-plan C5)

export type Habits = Schemas['HabitsView']
export type HabitKey = Schemas['Habit']

/** Today's habits with this week's count; null when not signed in. */
export async function fetchHabits(signal?: AbortSignal): Promise<Habits | null> {
  const res = await fetch('/api/habits', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Habits
}

/** Tick or untick one of today's habits; returns them all as they now are. */
export async function markHabit(habit: HabitKey, done: boolean): Promise<Habits> {
  const res = signedIn(
    await fetch(`/api/habits/${habit}`, {
      method: 'PUT',
      credentials: 'same-origin',
      headers: json,
      body: JSON.stringify({ done }),
    }),
  )
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as Habits
}

/** Everything stored about me, as a zip (needs a recent sign-in, like a passkey change). */
export const downloadExport = () => withFreshSignIn(downloadExportNow)

async function downloadExportNow(): Promise<Blob> {
  const res = await fetch('/api/account/export', { credentials: 'same-origin' })
  if (res.status === 403) throw new StaleSignInError()
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return res.blob()
}

/** Erase everything stored about me (ADR-0044); `confirm` is the word the person typed.
 *  Needs a recent sign-in; signs this browser out. */
export const eraseAllMyData = (confirm: string) => withFreshSignIn(() => eraseNow(confirm))

async function eraseNow(confirm: string): Promise<void> {
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
export const storeAiKey = (key: string) => withFreshSignIn(() => storeAiKeyNow(key))

async function storeAiKeyNow(key: string): Promise<AiStatus | KeyCheck> {
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

// ------------------------------------------------------- heart-rate zones (ADR-0055)

export type HeartRate = Schemas['HeartRateView']
export type HeartRateBody = Schemas['HeartRateBody']

/** My zones and what sets them; null when not signed in. */
export async function fetchHeartRate(signal?: AbortSignal): Promise<HeartRate | null> {
  const res = await fetch('/api/account/heart-rate', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as HeartRate
}

/** Save the birth year and own max heart rate; a string says what's wrong. */
export async function saveHeartRate(body: HeartRateBody): Promise<HeartRate | string> {
  const res = signedIn(
    await fetch('/api/account/heart-rate', {
      method: 'PUT',
      headers: json,
      body: JSON.stringify(body),
      credentials: 'same-origin',
    }),
  )
  if (res.status === 422) {
    const detail = ((await res.json()) as { detail?: unknown }).detail
    return typeof detail === 'string' ? detail : 'Check the numbers and try again.'
  }
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as HeartRate
}

// ------------------------------------------------------ band import secret (ADR-0055)

export type BandImport = Schemas['IngestView']
export type BandSecret = Schemas['NewSecret']

/** Whether a band import secret exists, when it was last used and where the phone posts. */
export async function fetchBandImport(signal?: AbortSignal): Promise<BandImport | null> {
  const res = await fetch('/api/account/ingest', { signal, credentials: 'same-origin' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as BandImport
}

/** A new secret for the phone, shown once. Needs a recent sign-in. */
export const makeBandSecret = () => withFreshSignIn(makeBandSecretNow)

async function makeBandSecretNow(): Promise<BandSecret> {
  const res = signedIn(
    await fetch('/api/account/ingest', { method: 'POST', credentials: 'same-origin' }),
  )
  if (res.status === 403) throw new StaleSignInError()
  if (!res.ok) throw new Error(`The server answered ${res.status}.`)
  return (await res.json()) as BandSecret
}

export async function removeBandSecret(): Promise<void> {
  const res = signedIn(
    await fetch('/api/account/ingest', { method: 'DELETE', credentials: 'same-origin' }),
  )
  if (res.status !== 204 && res.status !== 404)
    throw new Error(`The server answered ${res.status}.`)
}
