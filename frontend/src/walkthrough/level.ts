/**
 * The suggested level (ADR-0092, "How the plan is made" 1), worked out on this device from the
 * age, exercise and everyday answers. It only picks where each ladder's questions start; it is
 * never sent or stored, and the person's "can you do...?" answers decide every step.
 *
 * The values match `domain/walkthrough.py`, so the answers are kept as they are given here.
 */

export type AgeBand = '18-34' | '35-49' | '50-64' | '65-74' | '75+'
export type Often = 'not_now' | 'under_weekly' | 'one_two' | 'three_plus'
export type Effort = 'talk' | 'breathless'
export type HowLong = 'under_10' | '10_30' | 'over_30'

/** What screens 4-6 hold. Anything can be skipped: null. Everyday answers: true is yes. */
export interface About {
  age: AgeBand | null
  often: Often | null
  effort: Effort | null
  howLong: HowLong | null
  chair: boolean | null // stand up from a chair without your hands
  stairs: boolean | null // climb a flight of stairs without stopping
  walk: boolean | null // walk 10 minutes without stopping
  floor: boolean | null // get down to the floor and up again
}

export const NOTHING_ANSWERED: About = {
  age: null,
  often: null,
  effort: null,
  howLong: null,
  chair: null,
  stairs: null,
  walk: null,
  floor: null,
}

/** Never higher: the questions walk up from here. */
export const TOP = 4

/** The highest level each age band starts at. */
const AGE_CAP: Partial<Record<AgeBand, number>> = { '65-74': 3, '75+': 2 }

/** First match wins. A skipped answer (null) matches no line, so it lowers nothing. */
function uncapped(a: About): number {
  if (a.chair === false || a.walk === false) return 1
  if (a.stairs === false || a.often === 'not_now' || a.often === 'under_weekly') return 2
  if (a.often === 'one_two' || a.effort === 'talk' || a.howLong === 'under_10') return 3
  return TOP
}

/** The level each ladder's questions start at: 1 to 4. */
export function suggestedLevel(a: About): number {
  const cap = a.age ? AGE_CAP[a.age] : undefined
  return Math.min(uncapped(a), cap ?? TOP)
}
