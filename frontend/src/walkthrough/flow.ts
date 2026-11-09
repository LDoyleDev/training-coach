/**
 * The walk-through's screens, in order (ADR-0092, "The screens, in order"): one question per
 * screen, each with the number of the ADR's screen it belongs to, for the progress line. Every
 * answer is held in memory only; a reload starts again.
 */
import type { KitItemBody, MessageSettings } from '../api'
import { type Answer, QUESTIONS } from '../readiness/questions'
import type { About } from './level'

export type AvoidKey =
  'avoid_floor' | 'avoid_kneeling' | 'avoid_impact' | 'avoid_hanging' | 'avoid_knees'
export type Places = MessageSettings['places']

/** Everything answered so far, held in memory. Nothing here is sent until Save. */
export interface Draft {
  about: About
  safety: Record<string, Answer> // never sent: only that this version was answered (ADR-0085)
  avoid: Record<AvoidKey, boolean>
  places: Places
  kit: KitItemBody[] | null // null: no kit listed, so kit locks nothing
}

/** What the server already has, read as the walk-through opens: those screens are skipped. */
export interface Known {
  consent: boolean // the walkthrough category isn't open yet
  residence: boolean // no country yet
  safety: boolean // the health questions are due
}

/** The last screen of the progress line ("4 of 12"). */
export const LAST = 12

export const SAFETY = QUESTIONS.map((_, i) => `safety-${i}`)

/** Each screen's id and the ADR's screen number it belongs to. */
export const ORDER: { id: string; n: number }[] = [
  { id: 'welcome', n: 0 },
  { id: 'consent', n: 1 },
  { id: 'residence', n: 2 },
  ...SAFETY.map((id) => ({ id, n: 3 })),
  { id: 'safety-note', n: 3 },
  { id: 'age', n: 4 },
  { id: 'often', n: 5 },
  { id: 'effort', n: 5 },
  { id: 'howLong', n: 5 },
  { id: 'chair', n: 6 },
  { id: 'stairs', n: 6 },
  { id: 'walk', n: 6 },
  { id: 'floor', n: 6 },
  { id: 'avoid', n: 7 },
  { id: 'places', n: 8 },
  { id: 'kit', n: 8 },
  { id: 'next', n: 9 },
]

export const numberOf = (id: string) => ORDER.find((s) => s.id === id)?.n ?? 0

/** Whether a screen is asked: the server's screens only when needed, how hard and how long
 * only for someone who exercises now, and the home kit only for someone who trains at home. */
export function shown(id: string, known: Known, draft: Draft): boolean {
  if (id === 'consent') return known.consent
  if (id === 'residence') return known.residence
  if (id.startsWith('safety')) return known.safety
  if (id === 'effort' || id === 'howLong') return draft.about.often !== 'not_now'
  if (id === 'kit') return draft.places !== 'gym'
  return true
}

/** The next screen asked after `id`, or null at the end. */
export function after(id: string, known: Known, draft: Draft): string | null {
  const at = ORDER.findIndex((s) => s.id === id)
  return ORDER.slice(at + 1).find((s) => shown(s.id, known, draft))?.id ?? null
}

type Option<T> = { value: T; label: string }

/** A question answered with one tap, its answer kept in `About`. */
export interface Choice {
  key: keyof About
  title: string
  hint?: string
  options: Option<About[keyof About]>[]
}

const YES_NO: Option<boolean>[] = [
  { value: true, label: 'Yes' },
  { value: false, label: 'No' },
]

// The everyday and exercise-habit questions join #556's clinician list (ADR-0092, Decided 23).
export const CHOICES: Record<string, Choice> = {
  age: {
    key: 'age',
    title: 'How old are you?',
    options: [
      { value: '18-34', label: '18 to 34' },
      { value: '35-49', label: '35 to 49' },
      { value: '50-64', label: '50 to 64' },
      { value: '65-74', label: '65 to 74' },
      { value: '75+', label: '75 or over' },
    ],
  },
  often: {
    key: 'often',
    title: 'How often do you exercise now?',
    options: [
      { value: 'not_now', label: 'Not at the moment' },
      { value: 'under_weekly', label: 'Less than once a week' },
      { value: 'one_two', label: '1 or 2 times a week' },
      { value: 'three_plus', label: '3 or more times a week' },
    ],
  },
  effort: {
    key: 'effort',
    title: 'How hard, usually?',
    options: [
      { value: 'talk', label: 'Easy: I can talk in sentences' },
      { value: 'breathless', label: 'Sometimes out of breath' },
    ],
  },
  howLong: {
    key: 'howLong',
    title: 'How long, usually?',
    options: [
      { value: 'under_10', label: 'Under 10 minutes' },
      { value: '10_30', label: '10 to 30 minutes' },
      { value: 'over_30', label: 'Over 30 minutes' },
    ],
  },
  chair: {
    key: 'chair',
    title: 'Can you stand up from a chair without using your hands?',
    options: YES_NO,
  },
  stairs: {
    key: 'stairs',
    title: 'Can you climb a flight of stairs without stopping?',
    options: YES_NO,
  },
  walk: { key: 'walk', title: 'Can you walk for 10 minutes without stopping?', options: YES_NO },
  floor: { key: 'floor', title: 'Can you get down to the floor and up again?', options: YES_NO },
}
