/**
 * Safety wording, in one place to review (spec B7; ADR-0083, ADR-0084, ADR-0085).
 *
 * A CLINICIAN MUST CHECK THIS WORDING BEFORE ANYONE BUT THE OWNER USES THE APP (ADR-0085,
 * Consequences). It is general public-health text, the same for everyone: it names no
 * condition, never says "cleared", "safe for you" or "risk score", and stores nothing about
 * anyone's health. Sources: docs/specs/any-level-research.md Part 2, "Stop signs" and "Cardio",
 * and Part 5 (the European wording review, 1 Nov 2026).
 */
import type { CardioKind } from '../api'

/** What the app is for, as we state it (MDR intended purpose, ADR-0085): on Account, About. */
export const INTENDED_PURPOSE =
  'Training Coach is a general fitness app for adults living in the EU or EEA. It suggests ' +
  "exercises and sessions from your own choices and logs. It doesn't diagnose, prevent, " +
  "monitor, predict, treat or ease any disease or injury, and it doesn't assess your health or " +
  "whether you're fit to exercise. Its health questions and stop signs repeat public health " +
  'advice and suggest when to ask a doctor. You decide what you do.'

/** Before the stop signs, so they don't frighten anyone new (Reid et al. 2022). */
export const NORMAL =
  'Normal when you exercise: breathing harder, a faster and stronger heartbeat, sweating, and ' +
  'muscles that ache a little for a day or two.'

/** Stop signs (spec B7): what to look out for, and what to do. 112 works across the EU and EEA. */
export const STOP_SIGNS: { signs: string; then: string }[] = [
  {
    signs: 'Pain, pressure or tightness in your chest, or spreading to your arm, neck or jaw',
    then:
      "Stop and rest. Call 112 straight away if it's severe, or if it hasn't gone after 5 " +
      "minutes of rest. Don't drive yourself.",
  },
  {
    signs:
      'Feeling faint or dizzy, breathlessness far beyond what the effort explains, a racing or ' +
      "uneven heartbeat that doesn't calm down with rest, or a sudden change in your sight",
    then:
      "Stop and sit or lie down. Call 112 if you faint or it doesn't settle. Don't train " +
      'again that day, and talk to a doctor before you do.',
  },
  {
    signs: 'Sharp or sudden pain in a joint or muscle',
    then:
      'Stop that exercise. Try an easier step; if it still hurts, leave it out today. If it ' +
      "doesn't settle within a few days, get it checked.",
  },
  {
    signs:
      'Very dark (cola-coloured) urine, or muscles far more painful, swollen or weak than ' +
      'usual, in the days after a session',
    then: 'Get medical help the same day.',
  },
  {
    signs: 'A fever, or feeling ill',
    then: 'Skip training until you feel better, then start a little easier.',
  },
  {
    signs:
      "Bleeding, fluid leaking, or regular painful tightening of your bump, if you're pregnant",
    then: 'Stop and contact your midwife or doctor straight away.',
  },
]

/** After the stop signs. */
export const BODY_KNOWS = 'You know your body best: if something feels wrong, stop.'

/** The one-line reminder with every session and test day; the bot sends the same text
 * (`bot/messages.py` STOP, a backend test checks they match). One string literal, for that test. */
export const STOP_LINE =
  "Stop if you get chest pain or pressure, feel faint or dizzy, or are unusually out of breath. Call 112 if it's severe or doesn't ease with rest."

/** The talk test (Reed and Pipe 2014), shown instead of heart-rate zones when the person
 * turns it on (ADR-0083). */
export const TALK_TEST: string[] = [
  'Easy: you can sing.',
  'Moderate: you can talk in full sentences, but not sing.',
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
export const LAST_SET_LINE = "On exercises suited to it. Stop at the first rep that isn't clean."
export const LAST_SET_LOCKED = 'Available after your first 8 weeks'

/** The set screen's target for that set: its usual target is the floor. */
export const lastSetTarget = (target: string): string =>
  `Last set: at least ${target}, then as many good reps as you can`
