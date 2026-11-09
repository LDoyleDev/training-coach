import { useEffect, useState } from 'react'
import { answeredReadiness, fetchReadiness, SignedOutError, StaleQuestionsError } from '../api'
import { primary, secondary } from '../ui'
import NoteCard from './NoteCard'
import {
  ANSWER_LABELS,
  INTRO,
  noteFor,
  QUESTIONS,
  VERSION,
  type Answer,
  type Note,
} from './questions'

/** Pages that open without the check: signing in, the questions' own page, and the
 * walk-through, which asks them itself (ADR-0092). */
const UNCHECKED = ['/signin', '/readiness', '/start']
/** A slow or hung server never holds the app back for longer than this. */
const WAIT_MS = 4000

type Step =
  | { kind: 'checking' }
  | { kind: 'through' }
  | { kind: 'asking'; index: number }
  | { kind: 'answered'; note: Note; saved: 'saving' | 'saved' | 'failed' | 'stale' }

const answerButton = 'min-h-16 w-full rounded-2xl border-2 border-[var(--ink)] text-xl font-bold'

/**
 * Asked as the app opens (ADR-0085): when the health questions are due (never answered, a year
 * on, or the questions changed), they come first, one at a time, before the page that was
 * opened. "Not now" lets you through for this visit only. The note is worked out here and the
 * answers stay in memory: the server only hears that this version was answered. Signed out, an
 * error or a slow answer: straight through, the page handles it.
 */
export default function ReadinessGate({ children }: { children: React.ReactNode }) {
  const unchecked = UNCHECKED.includes(window.location.pathname)
  const [step, setStep] = useState<Step>({ kind: unchecked ? 'through' : 'checking' })
  const [answers, setAnswers] = useState<Record<string, Answer>>({})

  useEffect(() => {
    if (unchecked) return
    const ctrl = new AbortController()
    let gone = false // unmounted: a cancelled fetch decides nothing
    const timer = window.setTimeout(() => ctrl.abort(), WAIT_MS)
    fetchReadiness(ctrl.signal)
      .then((readiness) => {
        if (!gone) setStep(readiness?.due ? { kind: 'asking', index: 0 } : { kind: 'through' })
      })
      .catch(() => {
        if (!gone) setStep({ kind: 'through' })
      })
      .finally(() => window.clearTimeout(timer))
    return () => {
      gone = true
      window.clearTimeout(timer)
      ctrl.abort()
    }
  }, [unchecked])

  if (step.kind === 'through') return children

  const through = () => setStep({ kind: 'through' })
  const finish = (all: Record<string, Answer>) => {
    const note = noteFor(all)
    setStep({ kind: 'answered', note, saved: 'saving' })
    const saved = (result: 'saved' | 'failed' | 'stale') =>
      setStep((now) => (now.kind === 'answered' ? { ...now, saved: result } : now))
    answeredReadiness(VERSION)
      .then(() => saved('saved'))
      .catch((error: unknown) => {
        // Signed out meanwhile: they still see their note; the page asks to sign in after.
        if (error instanceof SignedOutError) saved('saved')
        else saved(error instanceof StaleQuestionsError ? 'stale' : 'failed')
      })
  }
  const pick = (index: number, value: Answer) => {
    const next = { ...answers, [QUESTIONS[index].key]: value }
    setAnswers(next)
    if (index + 1 < QUESTIONS.length) setStep({ kind: 'asking', index: index + 1 })
    else finish(next)
  }

  return (
    <div className="page">
      <main className="mt-4 flex flex-col gap-4">
        {step.kind === 'checking' && <p className="status">Loading…</p>}
        {step.kind === 'asking' && (
          <>
            <h1 className="text-2xl">Before you train</h1>
            <p className="m-0 text-[var(--slate)]">{INTRO}</p>
            <section aria-labelledby="question" className="flex flex-col gap-4">
              <p className="m-0 text-sm text-[var(--slate)]">
                Question {step.index + 1} of {QUESTIONS.length}
              </p>
              <p id="question" className="m-0 text-xl">
                {QUESTIONS[step.index].text}
              </p>
              {QUESTIONS[step.index].hint && (
                <p className="m-0 text-[var(--slate)]">{QUESTIONS[step.index].hint}</p>
              )}
              <div className="grid grid-cols-3 gap-3">
                {(['yes', 'no', 'not_sure'] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={answerButton}
                    onClick={() => pick(step.index, value)}
                  >
                    {ANSWER_LABELS[value]}
                  </button>
                ))}
              </div>
            </section>
            <div className="flex flex-wrap justify-between gap-2">
              {step.index > 0 ? (
                <button
                  type="button"
                  className={secondary}
                  onClick={() => setStep({ kind: 'asking', index: step.index - 1 })}
                >
                  Back
                </button>
              ) : (
                <span />
              )}
              <button type="button" className={secondary} onClick={through}>
                Not now
              </button>
            </div>
          </>
        )}
        {step.kind === 'answered' && (
          <>
            <NoteCard note={step.note} />
            {step.saved === 'failed' && (
              <p className="status-error m-0" role="alert">
                Couldn't save that you answered, so we'll ask again next time.
              </p>
            )}
            {step.saved === 'stale' && (
              <p className="status-error m-0" role="alert">
                The questions have changed since this page loaded. Reload to answer the new ones.
              </p>
            )}
            <button type="button" className={primary} onClick={through}>
              Continue
            </button>
          </>
        )}
      </main>
    </div>
  )
}
