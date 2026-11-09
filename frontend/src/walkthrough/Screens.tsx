import { useEffect, useState } from 'react'
import { StaleQuestionsError } from '../api'
import NoteCard from '../readiness/NoteCard'
import { ANSWER_LABELS, INTRO, noteFor, QUESTIONS } from '../readiness/questions'
import { primary, secondary } from '../ui'
import type { Draft } from './flow'

/** A one-tap answer, pressed when it's the one chosen (as Account's switches). */
const choice = (on: boolean) =>
  'min-h-14 w-full rounded-xl border-2 px-4 py-2 text-left text-lg font-bold ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

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
