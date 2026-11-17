/**
 * What Save sends (ADR-0092, "What runs in the browser"): the outcomes always, worked out here,
 * and the answers only with consent. The starter and the start day come from the tapped days on
 * this device, so without consent the days never leave it. The easy start goes with Save only:
 * the preview is the plan as it is, under one line (ADR-0094, Decided 11).
 */
import type { Outcomes, WalkAnswers, Walkthrough } from '../api'
import { avoided, type Draft, type Known, shown, walked } from './flow'
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
  easy: EasyStart
  body: Outcomes
}

/** Screen 13's easy-start switch (ADR-0094, Decided 4): as tapped, else as suggested. */
export interface EasyStart {
  on: boolean
  suggested: boolean
}

/** Screens 4-6's questions, each asked unless the answers before it skip it. */
const ABOUT = ['age', 'often', 'effort', 'howLong', 'chair', 'stairs', 'walk', 'floor'] as const

/** Suggested at a level of 3 or below, or when more than half of the questions on screens 4-6
 * that were asked were skipped (no answer, so no sign the person is used to training). */
export function easyStartOf(known: Known, draft: Draft): EasyStart {
  const asked = ABOUT.filter((id) => shown(id, known, draft))
  const skipped = asked.filter((id) => draft.about[id] === null).length
  const suggested = suggestedLevel(draft.about) <= 3 || skipped * 2 > asked.length
  return { on: draft.easyStart ?? suggested, suggested }
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
    easy: easyStartOf(known, draft),
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

/** The answers as given on the screens still asked: an answer on a screen later skipped (how
 * hard, once "not at the moment") and a ladder answer past where its walk now ends are left
 * out, as they no longer count. */
export function answersOf(known: Known, draft: Draft): WalkAnswers {
  const a = draft.about
  const asked = (id: string) => shown(id, known, draft)
  const placement = Object.fromEntries(
    known.ladders.flatMap((l) => {
      const found = walked(l, draft).asked
      return found.length ? [[l.slug, found.map(([step, answer]) => ({ step, answer }))]] : []
    }),
  )
  return {
    age_band: a.age,
    often: a.often,
    effort: asked('effort') ? a.effort : null,
    how_long: asked('howLong') ? a.howLong : null,
    chair: a.chair,
    stairs: a.stairs,
    walk: a.walk,
    floor: a.floor,
    weekdays: draft.days,
    placement,
  }
}
