import { useEffect, useState, type FormEvent } from 'react'
import { fetchReadiness, saveReadiness, SignedOutError, type Readiness } from '../api'
import AppShell from '../components/AppShell'
import SignedOutNotice from '../components/SignedOutNotice'
import { card, primary } from '../ui'
import { RetryCard, SignInCard } from '../components/StateCards'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; readiness: Readiness }

const CLEAR =
  "Thanks. Nothing in your answers says to hold back. You'll be asked again in about 6 months, " +
  'or sooner if your health changes: answer again any time.'
const SEE_DOCTOR =
  'Check with a doctor before hard efforts: the High-intensity session and test days. Until ' +
  'you have, the app reminds you on those days; keep them easy and stop well short of your limit.'

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

/** /readiness (ADR-0046): seven yes-or-no questions before hard exercise. Advice, not a gate. */
export default function ReadinessPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [answers, setAnswers] = useState<Record<string, boolean>>({})
  const [result, setResult] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [signedOut, setSignedOut] = useState(false) // the sign-in ended while on the page

  useEffect(() => {
    fetchReadiness()
      .then((readiness) => {
        if (readiness === null) return setLoaded({ status: 'signed-out' })
        setLoaded({ status: 'ready', readiness })
        setAnswers(readiness.answers ?? {})
      })
      .catch(() => setLoaded({ status: 'error' }))
  }, [])

  if (loaded.status !== 'ready') return <AppShell>{<Status loaded={loaded} />}</AppShell>
  const { questions, answered_at, ask_again_after } = loaded.readiness
  const complete = questions.every((q) => q.key in answers)

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setResult(null)
    setSignedOut(false) // a retry after signing in again
    try {
      const status = await saveReadiness(answers)
      setResult(status === 'see_doctor' ? SEE_DOCTOR : CLEAR)
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setResult("Couldn't save. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell>
      <h1>Readiness</h1>
      <p>
        Before hard exercise, a few questions about your health. A "yes" doesn't stop you training;
        it means a doctor should say hard efforts are fine first. This isn't medical advice.
      </p>
      {answered_at && ask_again_after && (
        <p className="text-[var(--slate)]">
          Answered {day(answered_at)}; asked again after {day(ask_again_after)}.
        </p>
      )}
      {signedOut && <SignedOutNotice />}
      <form onSubmit={save} className="flex flex-col gap-3">
        {questions.map((question) => (
          <fieldset key={question.key} className={card}>
            <legend className="sr-only">{question.text}</legend>
            <p aria-hidden="true">{question.text}</p>
            <div className="mt-2 flex gap-6">
              {[true, false].map((value) => (
                <label key={String(value)} className="flex min-h-11 items-center gap-2">
                  <input
                    type="radio"
                    name={question.key}
                    checked={answers[question.key] === value}
                    onChange={() => setAnswers({ ...answers, [question.key]: value })}
                  />
                  {value ? 'Yes' : 'No'}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <button type="submit" className={primary} disabled={!complete || busy}>
          Save my answers
        </button>
      </form>
      {result && (
        <p role="status" className={card}>
          {result}
        </p>
      )}
    </AppShell>
  )
}

function Status({ loaded }: { loaded: Exclude<Loaded, { status: 'ready' }> }) {
  if (loaded.status === 'loading')
    return (
      <p className="status" role="status">
        Loading…
      </p>
    )
  if (loaded.status === 'signed-out')
    return <SignInCard text="Sign in to answer the readiness questions." />
  return <RetryCard text="Couldn't load the questions. Check your connection." />
}
