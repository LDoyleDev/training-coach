/**
 * The health questions and their notes (ADR-0085), answered on this device only.
 *
 * A CLINICIAN MUST CHECK THIS WORDING BEFORE ANYONE BUT THE OWNER USES THE APP (ADR-0085,
 * Consequences). The answers and the note they lead to never leave the browser: the server
 * hears only that the questions were answered, and which VERSION. The words are research
 * Part 4, Recommendation 1 and Part 5 (`docs/specs/any-level-research.md`): never "cleared",
 * "safe for you" or a risk score; "we suggest" and "you decide".
 */

/** Bump with any change to the questions: the server's VERSION must match (a test checks). */
export const VERSION = 2

export type Answer = 'yes' | 'no' | 'not_sure'

export interface Question {
  key: string
  text: string
  hint?: string
}

export const QUESTIONS: Question[] = [
  {
    key: 'active',
    text: 'In the last 3 months, have you done planned exercise that made you breathe harder, on at least 3 days in most weeks?',
  },
  { key: 'age', text: 'Are you 35 or older?' },
  {
    key: 'heart',
    text: 'Has a doctor told you that you have a heart condition, or have you had a heart attack, a stent, heart surgery or a stroke?',
  },
  { key: 'diabetes_kidney', text: 'Do you have diabetes or kidney disease?' },
  {
    key: 'blood_pressure',
    text: 'Has a doctor told you that your blood pressure is high and not yet under control?',
  },
  {
    key: 'chest',
    text: 'In the last month, have you had pain, pressure or tightness in your chest, neck, jaw or arms, at rest or when active?',
  },
  {
    key: 'breath',
    text: 'Do you get unusually out of breath, or feel your heart racing or beating irregularly, with light effort such as walking or one flight of stairs?',
  },
  {
    key: 'faint',
    text: 'In the last 12 months, have you fainted, or fallen because you felt dizzy?',
    hint: 'Answer no if it was from breathing too fast, or right after an all-out effort.',
  },
  {
    key: 'supervised',
    text: 'Has a doctor told you to exercise only under supervision, or not to exercise for now?',
  },
  { key: 'pregnancy', text: 'Are you pregnant, or have you had a baby in the last 6 months?' },
]

export type Note = 'doctor_first' | 'easy_ask_before_hard' | 'easy'

const SYMPTOMS = ['chest', 'breath', 'faint', 'supervised', 'pregnancy']
const CONDITIONS = ['heart', 'diabetes_kidney', 'blood_pressure']

/** "Not sure" counts as the more careful answer: yes, or for the first question, no. */
const yes = (answers: Record<string, Answer>, key: string) => answers[key] !== 'no'

/** Which note the answers lead to (research Part 4, 1.4). Worked out here, never sent. */
export function noteFor(answers: Record<string, Answer>): Note {
  if (SYMPTOMS.some((key) => yes(answers, key))) return 'doctor_first'
  const inactive = answers.active !== 'yes'
  if (CONDITIONS.some((key) => yes(answers, key)) || (inactive && yes(answers, 'age')))
    return 'easy_ask_before_hard'
  return 'easy'
}

export const INTRO =
  'Some questions about your health before you train, asked once a year, or sooner if your ' +
  'health changes. A "yes" never stops you: it means we suggest talking to a doctor first. You ' +
  "decide. The app gives general suggestions; it can't examine you. Your answers stay on this " +
  'device.'

export const NOTES: Record<Note, { title: string; text: string }> = {
  doctor_first: {
    title: 'Talk to a doctor before you start',
    text:
      'We suggest you talk to a doctor before you start training with us. Tell them what you ' +
      "answered. If you're pregnant or had a baby recently, your midwife or doctor. You decide " +
      'what you do.',
  },
  easy_ask_before_hard: {
    title: 'Start easy, and ask a doctor before hard sessions',
    text:
      'Start easy and build up over weeks. Before hard sessions (High-intensity and test ' +
      'days), we suggest asking a doctor first. You decide.',
  },
  easy: {
    title: 'Start easy and build up',
    text: 'Start easy and build up a little at a time, over weeks.',
  },
}

/** Shown with every note, before the stop signs. */
export const WITH_EVERY_NOTE = [
  'If you have a fever or feel ill, wait until you feel better.',
  'If a joint gets worse with a movement, choose an easier step, or one of the preferences.',
  'After an operation, an injury or a serious illness, follow the advice you were given about ' +
    'when to start again, and answer these questions again.',
  "If your health changes, answer again. We'll ask again in a year.",
]

export const NOT_EXAMINED =
  "Training Coach gives general suggestions. It can't examine you and doesn't know your " +
  'health; you decide what you do.'

export const ANSWER_LABELS: Record<Answer, string> = {
  yes: 'Yes',
  no: 'No',
  not_sure: 'Not sure',
}
