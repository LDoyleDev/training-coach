/**
 * Safety wording, in one place to review (spec B7; ADR-0083, ADR-0084, ADR-0085).
 *
 * A CLINICIAN MUST CHECK THIS WORDING BEFORE ANYONE BUT THE OWNER USES THE APP (ADR-0085,
 * Consequences). It is general public-health text, the same for everyone: it names no
 * condition, never says "cleared", "safe for you" or "risk score", and stores nothing about
 * anyone's health. Sources: docs/specs/any-level-research.md Part 2, "Stop signs" and "Cardio".
 */
import type { CardioKind } from '../api'

/** Stop signs (spec B7): what to look out for, and what to do. */
export const STOP_SIGNS: { signs: string; then: string }[] = [
  {
    signs:
      'Chest, jaw or arm pain or pressure, dizziness or fainting, unusual breathlessness, ' +
      'or palpitations with any of these',
    then: "Stop and get help. Call 112 if it doesn't settle.",
  },
  { signs: 'Sharp joint pain', then: 'Stop and try an easier step.' },
  { signs: 'Very dark urine after a hard session', then: 'See a doctor.' },
]

/** The talk test (Reed and Pipe 2014), shown instead of heart-rate zones when the person
 * turns it on (ADR-0083). */
export const TALK_TEST: string[] = [
  'Easy: you can sing.',
  'Moderate: you can talk in full sentences.',
  'Hard: you can say only a few words.',
]

/** A cardio kind by the talk test: zone 2 is moderate, moderate cardio is hard. */
export const TALK_TEST_FOR: Partial<Record<CardioKind, string>> = {
  zone2: TALK_TEST[1],
  'moderate-cardio': TALK_TEST[2],
}
const TALK: Partial<Record<CardioKind, string>> = {
  zone2: 'Full sentences',
  'moderate-cardio': 'A few words',
}

/** How hard a cardio kind is, in the person's words: the talk test when it's on. */
export const effortLabel = (kind: CardioKind, talkTest: boolean, zones: string): string =>
  (talkTest && TALK[kind]) || zones

/** The breathing cue (ADR-0084), once each guided session. */
export const BREATHING = "Breathe out as you push; don't hold your breath."

/** Last set: as many good reps as you can (ADR-0084): only where the catalogue allows it, and
 * locked while a person is new. On Account, Today's length card and the set screen. */
export const LAST_SET = 'Last set: as many good reps as you can'
export const LAST_SET_LINE = "On exercises where it's safe. Stop at the first rep that isn't clean."
export const LAST_SET_LOCKED = 'Available after your first 8 weeks'

/** The set screen's target for that set: its usual target is the floor. */
export const lastSetTarget = (target: string): string =>
  `Last set: at least ${target}, then as many good reps as you can`
