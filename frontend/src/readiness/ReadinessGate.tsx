import { useEffect, useState } from 'react'
import { fetchReadiness, saveReadiness, SignedOutError, type Readiness } from '../api'
import type { ReadinessStatus } from '../api'
import { primary, secondary } from '../ui'
import { CLEAR, SEE_DOCTOR } from './advice'

/** Pages that open without the check: signing in, and the questions' own page. */
const UNCHECKED = ['/signin', '/readiness']
/** A slow or hung server never holds the app back for longer than this. */
const WAIT_MS = 4000

type Step =
  | { kind: 'checking' }
  | { kind: 'through' }
  | { kind: 'asking'; questions: Readiness['questions']; index: number }
  | { kind: 'saving' }
  | { kind: 'failed' }
  | { kind: 'answered'; status: ReadinessStatus }

const answer = 'min-h-16 w-full rounded-2xl border-2 border-[var(--ink)] text-xl font-bold'

/**
 * Asked as the app opens (UX plan, "Decided"): when the readiness questions are due (ADR-0046:
 * never answered, about 6 months on, or the questions changed), they come first, one at a
 * time, before the page that was opened. "Not now" lets you through for this visit only. Once
 * answered it says what that means for training, then Continue opens the page. Signed out, an
 * error or a slow answer: straight through, the page handles it.
 */
export default function ReadinessGate({ children }: { children: React.ReactNode }) {
  const unchecked = UNCHECKED.includes(window.location.pathname)
  const [step, setStep] = useState<Step>({ kind: unchecked ? 'through' : 'checking' })
  const [answers, setAnswers] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (unchecked) return
    const ctrl = new AbortController()
    let gone = false // unmounted: a cancelled fetch decides nothing
    const timer = window.setTimeout(() => ctrl.abort(), WAIT_MS)
    fetchReadiness(ctrl.signal)
      .then((readiness) => {
        if (gone) return
        setStep(
          readiness?.status === 'due' && readiness.questions.length > 0
            ? { kind: 'asking', questions: readiness.questions, index: 0 }
            : { kind: 'through' },
        )
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
  const save = async (all: Record<string, boolean>) => {
    setStep({ kind: 'saving' })
    try {
      setStep({ kind: 'answered', status: await saveReadiness(all) })
    } catch (error) {
      // Signed out meanwhile: the page asks to sign in. Anything else: say so, let them retry.
      setStep(error instanceof SignedOutError ? { kind: 'through' } : { kind: 'failed' })
    }
  }
  const pick = (questions: Readiness['questions'], index: number, value: boolean) => {
    const next = { ...answers, [questions[index].key]: value }
    setAnswers(next)
    if (index + 1 < questions.length) setStep({ kind: 'asking', questions, index: index + 1 })
    else void save(next)
  }
  const notNow = (
    <button type="button" className={secondary} onClick={through}>
      Not now
    </button>
  )

  return (
    <div className="page">
      <main className="mt-4 flex flex-col gap-4">
        {step.kind === 'checking' && <p className="status">Loading…</p>}
        {step.kind === 'asking' && (
          <>
            <h1 className="text-2xl">Before you train</h1>
            <p className="m-0 text-[var(--slate)]">
              A few health questions, asked about every 6 months. A "yes" doesn't stop you training.
              This isn't medical advice.
            </p>
            <section aria-labelledby="question" className="flex flex-col gap-4">
              <p className="m-0 text-sm text-[var(--slate)]">
                Question {step.index + 1} of {step.questions.length}
              </p>
              <p id="question" className="m-0 text-xl">
                {step.questions[step.index].text}
              </p>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((value) => (
                  <button
                    key={String(value)}
                    type="button"
                    className={answer}
                    onClick={() => pick(step.questions, step.index, value)}
                  >
                    {value ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </section>
            <div className="flex flex-wrap justify-between gap-2">
              {step.index > 0 ? (
                <button
                  type="button"
                  className={secondary}
                  onClick={() => setStep({ ...step, index: step.index - 1 })}
                >
                  Back
                </button>
              ) : (
                <span />
              )}
              {notNow}
            </div>
          </>
        )}
        {step.kind === 'saving' && (
          <p className="status" role="status">
            Saving…
          </p>
        )}
        {step.kind === 'failed' && (
          <>
            <p className="status-error m-0" role="alert">
              Couldn't save your answers. Check your connection and try again.
            </p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className={secondary} onClick={() => void save(answers)}>
                Try again
              </button>
              {notNow}
            </div>
          </>
        )}
        {step.kind === 'answered' && (
          <>
            <h1 className="text-2xl">
              {step.status === 'see_doctor' ? 'Go easier on hard days' : 'Go as planned'}
            </h1>
            <p role="status" className="m-0">
              {step.status === 'see_doctor' ? SEE_DOCTOR : CLEAR}
            </p>
            <button type="button" className={primary} onClick={through}>
              Continue
            </button>
          </>
        )}
      </main>
    </div>
  )
}
