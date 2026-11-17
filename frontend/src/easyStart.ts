/**
 * The easy start's words (ADR-0094), the same on the walk-through, Account, Today and Plan: a
 * lighter first 6 weeks or more, then the plan as it is.
 */

export const EASY_START = 'Easy start: lighter first weeks, less soreness'
export const EASY_START_LINE =
  'One set of each exercise at first, then one set fewer, for 6 weeks or more.'
/** At a suggested level of 4, where it starts off (Decided 4). */
export const EASY_START_NEW = 'New to strength work? Turn this on.'

/** Today's word after an offer is taken: a restart, or one more easy week of a phase. */
export const EASY_TAKEN = {
  restart: 'The easy start begins again with your next session.',
  light: 'One more easy week: one set of each.',
  lower: 'One more easy week: one set fewer of each.',
}

/** "31 Dec", from "2026-12-31". */
const short = (day: string) => {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

/** The line over a plan that shows more than the easy start does (Decided 11): until the day it
 * can be over, or for the first 6 weeks or more before the first workout (no day yet). */
export const lighterLine = (overFrom: string | null) =>
  overFrom
    ? `Lighter until at least ${short(overFrom)} (easy start); this is the plan from then.`
    : 'Lighter for the first 6 weeks or more (easy start); this is the plan from then.'
