/**
 * The walk-through's screens, in order (ADR-0092, "The screens, in order"): one question per
 * screen, each with the number of the ADR's screen it belongs to, for the progress line. Every
 * answer is held in memory only; a reload starts again.
 */
import { type Answer, QUESTIONS } from '../readiness/questions'

/** Everything answered so far, held in memory. Nothing here is sent until Save. */
export interface Draft {
  safety: Record<string, Answer> // never sent: only that this version was answered (ADR-0085)
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
  { id: 'next', n: 4 },
]

export const numberOf = (id: string) => ORDER.find((s) => s.id === id)?.n ?? 0

/** Whether a screen is asked: the server's screens only when it has no answer yet. */
export function shown(id: string, known: Known, _draft: Draft): boolean {
  if (id === 'consent') return known.consent
  if (id === 'residence') return known.residence
  if (id.startsWith('safety')) return known.safety
  return true
}

/** The next screen asked after `id`, or null at the end. */
export function after(id: string, known: Known, draft: Draft): string | null {
  const at = ORDER.findIndex((s) => s.id === id)
  return ORDER.slice(at + 1).find((s) => shown(s.id, known, draft))?.id ?? null
}
