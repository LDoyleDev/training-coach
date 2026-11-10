/**
 * What the plan screen previews and Save sends (ADR-0092, "What runs in the browser"): the
 * outcomes, worked out here. The starter and the start day come from the tapped days on
 * this device, so without consent the days never leave it.
 */
import type { Outcomes, Walkthrough } from '../api'
import { avoided, type Draft, type Known, walked } from './flow'
import { suggestedLevel } from './level'
import { type Start, startDay, starterDays } from './days'

type Starter = Walkthrough['starters'][number]

/** A level of 1 leaves the split squat out for now (S1 Decided 3); the person can put it back. */
export const LEFT_OUT = 'bulgarian-split-squat'

/** "2026-11-16", a local day as the API takes it. */
export const iso = (day: Date) =>
  `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`

/** "2026-11-16" back to a local day at midnight. */
export const local = (day: string) => {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export interface Picked {
  starter: Starter
  start: Start
  leftOut: string[]
  body: Outcomes
}

/** The step each exercise starts on: the one picked on the plan screen, else where its walk
 * placed it (the bottom when nothing was asked). */
export function stepsOf(known: Known, draft: Draft): Record<string, number> {
  return Object.fromEntries(
    known.ladders.map((l) => [l.slug, draft.chosen[l.slug] ?? l.steps[walked(l, draft).placed].id]),
  )
}

/** The outcomes of the walk, as the preview and Save take them. */
export function pick(known: Known, starters: Starter[], draft: Draft, today: Date): Picked {
  const days = starterDays(draft.days.length)
  const starter = starters.find((s) => s.days === days) ?? starters[0]
  const start = startDay(
    today,
    draft.days,
    starter.sessions.map((s) => s.rest_after),
  )
  const leftOut = suggestedLevel(draft.about) === 1 && !draft.putBack ? [LEFT_OUT] : []
  return {
    starter,
    start,
    leftOut,
    body: {
      starter: starter.slug,
      steps: stepsOf(known, draft),
      starts_on: iso(start.on),
      places: draft.places,
      kit: draft.places === 'gym' ? null : draft.kit, // gym only: the home kit isn't asked
      avoid: avoided(draft) as Outcomes['avoid'],
      session_minutes: draft.minutes as Outcomes['session_minutes'],
      session_exercises: draft.count as Outcomes['session_exercises'],
      left_out: leftOut,
    },
  }
}
