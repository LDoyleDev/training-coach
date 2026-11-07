import { useEffect, useState, type FormEvent } from 'react'
import {
  answeredReadiness,
  fetchReadiness,
  SignedOutError,
  StaleQuestionsError,
  type Readiness,
} from '../api'
import AppShell from '../components/AppShell'
import SignedOutNotice from '../components/SignedOutNotice'
import { card, primary } from '../ui'
import { RetryCard, SignInCard } from '../components/StateCards'
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

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; readiness: Readiness }

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

/** /readiness (ADR-0085): ten health questions, answered here. The answers and the note stay
 * on this device; the server hears only that they were answered. Advice, never a gate. */
export default function ReadinessPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [answers, setAnswers] = useState<Record<string, Answer>>({})
  const [note, setNote] = useState<Note | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [signedOut, setSignedOut] = useState(false) // the sign-in ended while on the page

  useEffect(() => {
    fetchReadiness()
      .then((readiness) =>
        setLoaded(readiness === null ? { status: 'signed-out' } : { status: 'ready', readiness }),
      )
      .catch(() => setLoaded({ status: 'error' }))
  }, [])

  if (loaded.status !== 'ready') return <AppShell>{<Status loaded={loaded} />}</AppShell>
  const { answered_at, ask_again_after } = loaded.readiness
  const complete = QUESTIONS.every((q) => q.key in answers)

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setProblem(null)
    setSignedOut(false) // a retry after signing in again
    setNote(noteFor(answers)) // the note doesn't wait for the server: it's worked out here
    try {
      setLoaded({ status: 'ready', readiness: await answeredReadiness(VERSION) })
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else if (error instanceof StaleQuestionsError)
        setProblem(
          'The questions have changed since this page loaded. Reload to answer the new ones.',
        )
      else setProblem("Couldn't save that you answered. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell>
      <h1>Readiness</h1>
      <p>{INTRO}</p>
      {answered_at && ask_again_after && (
        <p className="text-[var(--slate)]">
          Answered {day(answered_at)}; asked again after {day(ask_again_after)}.
        </p>
      )}
      {signedOut && <SignedOutNotice />}
      <form onSubmit={save} className="flex flex-col gap-3">
        {QUESTIONS.map((question) => (
          <fieldset key={question.key} className={card}>
            <legend className="sr-only">{question.text}</legend>
            <p aria-hidden="true">{question.text}</p>
            {question.hint && <p className="text-[var(--slate)]">{question.hint}</p>}
            <div className="mt-2 flex flex-wrap gap-6">
              {(['yes', 'no', 'not_sure'] as const).map((value) => (
                <label key={value} className="flex min-h-11 items-center gap-2">
                  <input
                    type="radio"
                    name={question.key}
                    checked={answers[question.key] === value}
                    onChange={() => setAnswers({ ...answers, [question.key]: value })}
                  />
                  {ANSWER_LABELS[value]}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <button type="submit" className={primary} disabled={!complete || busy}>
          See what we suggest
        </button>
      </form>
      {note && <NoteCard note={note} />}
      {problem && (
        <p role="alert" className="status-error">
          {problem}
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
    return <SignInCard text="Sign in to answer the health questions." />
  return <RetryCard text="Couldn't load the questions. Check your connection." />
}
