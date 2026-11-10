import { useEffect, useState } from 'react'
import { type Equipment, type KitItemBody, StaleQuestionsError } from '../api'
import { label } from '../account/kit'
import { type Editing, KitList } from '../account/MyEquipment'
import NoteCard from '../readiness/NoteCard'
import { ANSWER_LABELS, INTRO, noteFor, QUESTIONS } from '../readiness/questions'
import { primary, secondary } from '../ui'
import Figure from '../figures/Figure'
import type { WalkLadder, WalkStep } from './api'
import { type AvoidKey, type Draft, type Places, WEEKDAYS } from './flow'
import type { CanDo } from './walk'

/** A one-tap answer, pressed when it's the one chosen (as Account's switches). */
const choice = (on: boolean) =>
  'min-h-14 w-full rounded-xl border-2 px-4 py-2 text-left text-lg font-bold ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

/** A choice with a second line under its name. (Not Tailwind's `block`: index.css has its own
 * `.block`, a page section with a rule above it.) */
const lines = ' flex flex-col items-start justify-center'

export function Welcome({ onStart }: { onStart: () => void }) {
  return (
    <>
      <h1 className="m-0 text-3xl font-extrabold">Set up your plan</h1>
      <p className="m-0">
        A few questions, about 10 minutes, so every exercise starts at a step that suits you. Skip
        anything you'd rather not answer.
      </p>
      <p className="m-0">
        Nothing changes until you see your plan at the end and save it. You can change anything
        before then.
      </p>
      <p className="m-0 text-sm text-[var(--slate)]">
        Training Coach is a private test for invited family and friends.
      </p>
      <button type="button" className={primary} onClick={onStart}>
        Start
      </button>
    </>
  )
}

/** One question, one tap: the answer moves on. Skip moves on without one. */
export function ChoiceScreen<T>({
  question,
  value,
  onAnswer,
  onSkip,
}: {
  question: { title: string; hint?: string; options: { value: T; label: string }[] }
  value: T
  onAnswer: (value: T) => void
  onSkip: () => void
}) {
  return (
    <>
      <h1 className="m-0 text-2xl">{question.title}</h1>
      {question.hint && <p className="m-0 text-[var(--slate)]">{question.hint}</p>}
      <div className="flex flex-col gap-2">
        {question.options.map((o) => (
          <button
            key={String(o.value)}
            type="button"
            aria-pressed={value === o.value}
            className={choice(value === o.value)}
            onClick={() => onAnswer(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
      <button type="button" className={`${secondary} self-start`} onClick={onSkip}>
        Skip
      </button>
    </>
  )
}

/** One of the ten health questions (ADR-0085): the answer stays in this browser. */
export function SafetyQuestion({
  index,
  value,
  onAnswer,
  onSkip,
}: {
  index: number
  value: string | undefined
  onAnswer: (value: 'yes' | 'no' | 'not_sure') => void
  onSkip: () => void
}) {
  const question = QUESTIONS[index]
  return (
    <>
      {index === 0 && <p className="m-0 text-[var(--slate)]">{INTRO}</p>}
      <p className="m-0 text-sm text-[var(--slate)]">
        Health question {index + 1} of {QUESTIONS.length}
      </p>
      <h1 className="m-0 text-xl">{question.text}</h1>
      {question.hint && <p className="m-0 text-[var(--slate)]">{question.hint}</p>}
      <div className="grid grid-cols-3 gap-3">
        {(['yes', 'no', 'not_sure'] as const).map((answer) => (
          <button
            key={answer}
            type="button"
            aria-pressed={value === answer}
            className={choice(value === answer) + ' text-center'}
            onClick={() => onAnswer(answer)}
          >
            {ANSWER_LABELS[answer]}
          </button>
        ))}
      </div>
      <button type="button" className={`${secondary} self-start`} onClick={onSkip}>
        Not now
      </button>
    </>
  )
}

/** The note the health answers lead to, worked out here. The server hears only that this
 * version was answered, as the readiness page tells it: `tell` does it once a walk-through. */
export function SafetyNote({
  answers,
  tell,
  onNext,
}: {
  answers: Draft['safety']
  tell: () => Promise<unknown> | null
  onNext: () => void
}) {
  const [problem, setProblem] = useState<string | null>(null)
  useEffect(() => {
    tell()?.catch((error: unknown) =>
      setProblem(
        error instanceof StaleQuestionsError
          ? 'The questions have changed since this page loaded. Reload to answer the new ones.'
          : "Couldn't save that you answered, so we'll ask again next time.",
      ),
    )
  }, [tell])
  return (
    <>
      <h1 className="sr-only">What we suggest</h1>
      <NoteCard note={noteFor(answers)} />
      {problem && (
        <p className="status-error m-0" role="alert">
          {problem}
        </p>
      )}
      <button type="button" className={primary} onClick={onNext}>
        Next
      </button>
    </>
  )
}

/** The avoid switches (ADR-0083), off until tapped; the floor one marked suggested after a no
 * to the floor question. A preference: no reason is asked. */
const AVOID: { key: AvoidKey; label: string }[] = [
  { key: 'avoid_floor', label: 'Keep me off the floor' },
  { key: 'avoid_kneeling', label: 'No kneeling' },
  { key: 'avoid_impact', label: 'No jumping or running' },
  { key: 'avoid_hanging', label: 'No hanging' },
  { key: 'avoid_knees', label: 'Easy on my knees' },
]

export function AvoidScreen({
  draft,
  onChange,
  onNext,
}: {
  draft: Draft
  onChange: (avoid: Draft['avoid']) => void
  onNext: () => void
}) {
  return (
    <>
      <h1 className="m-0 text-2xl">Anything you'd rather avoid?</h1>
      <p className="m-0 text-[var(--slate)]">
        You choose what you're ready for. These skip the steps that need it, and you can change them
        on Account at any time.
      </p>
      <div className="flex flex-col gap-2">
        {AVOID.map(({ key, label }) => {
          const on = draft.avoid[key]
          const suggested = key === 'avoid_floor' && draft.about.floor === false
          return (
            <button
              key={key}
              type="button"
              aria-pressed={on}
              className={choice(on) + lines}
              onClick={() => onChange({ ...draft.avoid, [key]: !on })}
            >
              {label}
              <span className="font-normal">
                {on ? 'On' : 'Off'}
                {suggested && ' · Suggested'}
              </span>
            </button>
          )
        })}
      </div>
      <button type="button" className={primary} onClick={onNext}>
        Next
      </button>
    </>
  )
}

/** Where the person trains (ADR-0071), as Account says it. */
const PLACES: { places: Places; label: string; line: string }[] = [
  { places: 'home', label: 'Home', line: 'With the kit you have there.' },
  { places: 'gym', label: 'Gym', line: 'A gym has everything.' },
  { places: 'both', label: 'Both', line: 'You pick home or gym on the day.' },
]

export function PlacesScreen({
  value,
  onAnswer,
}: {
  value: Places
  onAnswer: (places: Places) => void
}) {
  return (
    <>
      <h1 className="m-0 text-2xl">Where will you train?</h1>
      <div className="flex flex-col gap-2">
        {PLACES.map(({ places, label, line }) => (
          <button
            key={places}
            type="button"
            aria-pressed={value === places}
            className={choice(value === places) + lines}
            onClick={() => onAnswer(places)}
          >
            {label}
            <span className="font-normal">{line}</span>
          </button>
        ))}
      </div>
    </>
  )
}

/** What's at home: My equipment's list, held in memory until Save. */
export function KitScreen({
  kinds,
  kit,
  onChange,
  onNext,
}: {
  kinds: Equipment['kinds']
  kit: KitItemBody[] | null
  onChange: (kit: KitItemBody[]) => void
  onNext: () => void
}) {
  const [editing, setEditing] = useState<Editing | null>(null)
  const names = new Map(kinds.map((k) => [k.kit, k.name]))
  const items = (kit ?? []).map((body) => ({
    ...body,
    label: label(body, names.get(body.kit) ?? body.kit),
  }))
  const shown: Equipment = { items, kinds, listed: kit !== null, saved_at: null }
  return (
    <>
      <h1 className="m-0 text-2xl">What do you have at home?</h1>
      <p className="m-0 text-[var(--slate)]">
        Steps that need kit you don't have aren't asked. Household things, a chair, a wall or a
        towel, need nothing here.
      </p>
      <KitList
        kit={shown}
        editing={editing}
        setEditing={setEditing}
        busy={false}
        refused={null}
        unlocks={false}
        save={(next) => {
          onChange(next)
          setEditing(null)
        }}
      />
      <button type="button" className={primary} onClick={onNext}>
        Next
      </button>
    </>
  )
}

const CAN_DO: { answer: Exclude<CanDo, 'skip'>; label: string }[] = [
  { answer: 'yes', label: 'Yes' },
  { answer: 'no', label: 'No' },
  { answer: 'not_sure', label: 'Not sure' },
]

/** One "Can you do...?" question (ADR-0092, screen 9): the step's figure and cue, then Yes, No,
 * Not sure (counted as No) or Skip this one (the exercise starts at its bottom step). */
export function LadderScreen({
  ladder,
  step,
  index,
  of,
  value,
  onAnswer,
}: {
  ladder: WalkLadder
  step: WalkStep
  index: number // which exercise of the ladders
  of: number
  value: CanDo | undefined
  onAnswer: (answer: CanDo) => void
}) {
  return (
    <>
      <p className="m-0 text-sm text-[var(--slate)]">
        {ladder.name}, exercise {index + 1} of {of}
      </p>
      <h1 className="m-0 text-2xl">{step.question}</h1>
      <Figure slug={ladder.slug} name={step.name} step={step.name} />
      {step.cue && <p className="m-0">{step.cue}</p>}
      <p className="m-0 text-[var(--slate)]">Not sure? Try one now, holding a counter.</p>
      <div className="grid grid-cols-3 gap-3">
        {CAN_DO.map(({ answer, label }) => (
          <button
            key={answer}
            type="button"
            aria-pressed={value === answer}
            className={choice(value === answer) + ' text-center'}
            onClick={() => onAnswer(answer)}
          >
            {label}
          </button>
        ))}
      </div>
      <button
        type="button"
        aria-pressed={value === 'skip'}
        className={`${secondary} self-start`}
        onClick={() => onAnswer('skip')}
      >
        Skip this one
      </button>
    </>
  )
}

/** Screen 10: the weekdays that suit, tapped on and off. The plan screen works out the starter
 * and the start day from them (ADR-0092, How the plan is made 3 and 8). */
export function DaysScreen({
  days,
  onChange,
  onNext,
}: {
  days: number[]
  onChange: (days: number[]) => void
  onNext: () => void
}) {
  const toggle = (day: number) =>
    onChange(
      days.includes(day) ? days.filter((d) => d !== day) : [...days, day].sort((a, b) => a - b),
    )
  return (
    <>
      <h1 className="m-0 text-2xl">Which days suit you to train?</h1>
      <p className="m-0 text-[var(--slate)]">Tap each one. You can change them later.</p>
      <div className="flex flex-col gap-2">
        {WEEKDAYS.map((name, day) => (
          <button
            key={name}
            type="button"
            aria-pressed={days.includes(day)}
            className={choice(days.includes(day))}
            onClick={() => toggle(day)}
          >
            {name}
          </button>
        ))}
      </div>
      <button type="button" className={primary} onClick={onNext}>
        Next
      </button>
    </>
  )
}
