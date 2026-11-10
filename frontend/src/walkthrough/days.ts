/**
 * The starter and the start day from the tapped weekdays (ADR-0092, How the plan is made 3 and
 * 8), a TS copy of `domain/walkthrough.py`'s `starter_days`, `landing` and `start_day`. The
 * tapped days are an answer, so without consent they never reach the server (Decided 8): the
 * browser picks, and Save sends only the starter and the start day. Weekdays are 0 Monday to 6
 * Sunday, as Python's `date.weekday()`; dates are local days at midnight.
 */

/** The days a week of the starter for `tapped` weekdays: 1 or 2 the 2-day, 3 the 3-day, 4 or
 * more the 4-day; none the 3-day, starting tomorrow. */
export function starterDays(tapped: number): number {
  if (tapped === 0) return 3
  return Math.min(Math.max(tapped, 2), 4)
}

const plus = (day: Date, days: number) =>
  new Date(day.getFullYear(), day.getMonth(), day.getDate() + days)

/** 0 Monday to 6 Sunday. */
export const weekday = (day: Date) => (day.getDay() + 6) % 7

/** The day each of a starter's sessions lands on, the first on `start` and each next one after
 * the rest places before it (ADR-0091). */
export function landing(start: Date, restAfter: readonly number[]): Date[] {
  const days: Date[] = []
  let day = start
  for (const rest of restAfter) {
    days.push(day)
    day = plus(day, 1 + rest)
  }
  return days
}

export interface Start {
  on: Date
  missed: number[] // tapped weekdays no session lands on, Monday first
}

/** Of the next week's tapped days, today included, the first from which the starter's rest
 * places land the most sessions on tapped days, with the tapped days no session lands on. None
 * tapped: tomorrow. */
export function startDay(
  today: Date,
  weekdays: readonly number[],
  restAfter: readonly number[],
): Start {
  const from = plus(today, 0) // midnight
  if (weekdays.length === 0) return { on: plus(from, 1), missed: [] }
  const tapped = new Set(weekdays)
  const hits = (start: Date) => landing(start, restAfter).filter((d) => tapped.has(weekday(d)))
  const candidates = [0, 1, 2, 3, 4, 5, 6]
    .map((k) => plus(from, k))
    .filter((d) => tapped.has(weekday(d)))
  // The earliest of equals, as Python's max.
  const best = candidates.reduce((a, b) => (hits(b).length > hits(a).length ? b : a))
  const landed = new Set(landing(best, restAfter).map(weekday))
  const missed = [...tapped].filter((d) => !landed.has(d)).sort((a, b) => a - b)
  return { on: best, missed }
}
