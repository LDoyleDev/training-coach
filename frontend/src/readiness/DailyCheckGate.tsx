import { useEffect, useState } from 'react'
import {
  changeToday,
  fetchDailyCheck,
  fetchToday,
  saveDailyCheck,
  SignedOutError,
  type DailyCheck,
  type DailyCheckAnswers,
} from '../api'
import { primary, secondary } from '../ui'

/** Pages that open without the check: signing in, and the readiness questions' own page. */
const UNCHECKED = ['/signin', '/readiness']
/** A slow or hung server never holds the app back for longer than this. */
const WAIT_MS = 4000

type Step =
  | { kind: 'checking' }
  | { kind: 'through' }
  | { kind: 'asking'; check: DailyCheck; index: number }
  | { kind: 'saving'; check: DailyCheck }
  | { kind: 'failed'; check: DailyCheck }
  | { kind: 'advice'; check: DailyCheck }
  | { kind: 'resting' }
  | { kind: 'rested'; text: string }

const answer = 'min-h-16 w-full rounded-2xl border-2 border-[var(--ink)] text-xl font-bold'

/** Rest today's session (the same rest as on Today, ADR-0052): what happened, in words. */
async function restToday(): Promise<string> {
  const today = await fetchToday()
  if (!today?.session) return 'Nothing is left to train today, so enjoy the rest.'
  const changed = await changeToday('rest', today.session.template_id)
  if (changed === 'stale')
    return "Today's session changed meanwhile, so nothing was rested. Have a look on Today."
  return changed.advanced
    ? `${changed.session} logged as a rest day. Enjoy it.`
    : `Rest today. ${changed.session} moves to tomorrow.`
}

/**
 * The daily check (ADR-0053), asked as the app opens once the readiness questions are out of
 * the way: how you slept, how sore you are, your energy, one tap each, then what that means
 * for today. On "Take a rest day" it offers Rest today. "Not now" lets you through for this
 * visit only; once answered it isn't asked again today. Signed out, an error or a slow
 * answer: straight through, the page handles it.
 */
export default function DailyCheckGate({ children }: { children: React.ReactNode }) {
  const unchecked = UNCHECKED.includes(window.location.pathname)
  const [step, setStep] = useState<Step>({ kind: unchecked ? 'through' : 'checking' })
  const [answers, setAnswers] = useState<Record<string, string>>({})

  useEffect(() => {
    if (unchecked) return
    const ctrl = new AbortController()
    let gone = false // unmounted: a cancelled fetch decides nothing
    const timer = window.setTimeout(() => ctrl.abort(), WAIT_MS)
    fetchDailyCheck(ctrl.signal)
      .then((check) => {
        if (gone) return
        setStep(
          check && !check.answers && check.questions.length > 0
            ? { kind: 'asking', check, index: 0 }
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
  const save = async (check: DailyCheck, all: Record<string, string>) => {
    setStep({ kind: 'saving', check })
    try {
      // Every key was answered from the questions the server sent.
      setStep({ kind: 'advice', check: await saveDailyCheck(all as DailyCheckAnswers) })
    } catch (error) {
      setStep(error instanceof SignedOutError ? { kind: 'through' } : { kind: 'failed', check })
    }
  }
  const pick = (check: DailyCheck, index: number, value: string) => {
    const next = { ...answers, [check.questions[index].key]: value }
    setAnswers(next)
    if (index + 1 < check.questions.length) setStep({ kind: 'asking', check, index: index + 1 })
    else void save(check, next)
  }
  const rest = async () => {
    setStep({ kind: 'resting' })
    try {
      setStep({ kind: 'rested', text: await restToday() })
    } catch (error) {
      if (error instanceof SignedOutError) return through()
      setStep({ kind: 'rested', text: "Couldn't rest today. You can still do it from Today." })
    }
  }
  const notNow = (
    <button type="button" className={secondary} onClick={through}>
      Not now
    </button>
  )
  const advice = step.kind === 'advice' ? step.check.advice : null

  return (
    <div className="page">
      <main className="mt-4 flex flex-col gap-4">
        {step.kind === 'checking' && <p className="status">Loading…</p>}
        {step.kind === 'asking' && (
          <>
            <h1 className="text-2xl">How's today?</h1>
            <section aria-labelledby="question" className="flex flex-col gap-4">
              <p className="m-0 text-sm text-[var(--slate)]">
                Question {step.index + 1} of {step.check.questions.length}
              </p>
              <p id="question" className="m-0 text-xl">
                {step.check.questions[step.index].text}
              </p>
              <div className="flex flex-col gap-3">
                {step.check.questions[step.index].options.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={answer}
                    onClick={() => pick(step.check, step.index, option.value)}
                  >
                    {option.label}
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
        {(step.kind === 'saving' || step.kind === 'resting') && (
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
              <button
                type="button"
                className={secondary}
                onClick={() => void save(step.check, answers)}
              >
                Try again
              </button>
              {notNow}
            </div>
          </>
        )}
        {advice && (
          <>
            <h1 className="text-2xl">{advice.title}</h1>
            <p role="status" className="m-0">
              {advice.text}
            </p>
            {advice.kind === 'rest' && (
              <button type="button" className={primary} onClick={() => void rest()}>
                Rest today
              </button>
            )}
            <button
              type="button"
              className={advice.kind === 'rest' ? secondary : primary}
              onClick={through}
            >
              Continue
            </button>
          </>
        )}
        {step.kind === 'rested' && (
          <>
            <p role="status" className="m-0">
              {step.text}
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
