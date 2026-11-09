import { useCallback, useEffect, useRef, useState } from 'react'
import { answeredReadiness, fetchConsents, fetchMe, fetchReadiness, fetchResidence } from '../api'
import Residence from '../account/Residence'
import { RetryCard, SignInCard } from '../components/StateCards'
import { ConsentCard } from '../consent/Consented'
import { QUESTIONS, VERSION } from '../readiness/questions'
import { card, primary, secondary } from '../ui'
import { after, type Draft, type Known, LAST, numberOf, SAFETY } from './flow'
import { SafetyNote, SafetyQuestion, Welcome } from './Screens'

interface Ready {
  owner: boolean // the owner's try-out: nothing changes his plan (ADR-0092)
  known: Known
  answeredAt: string | null // when the health questions were last answered
  draft: Draft
}

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; ready: Ready }

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

async function load(signal: AbortSignal): Promise<Ready | null> {
  const [me, consents, residence, readiness] = await Promise.all([
    fetchMe(signal),
    fetchConsents(signal),
    fetchResidence(signal),
    fetchReadiness(signal),
  ])
  if (!me || !consents || !residence || !readiness) return null
  const walkthrough = consents.categories.find((c) => c.category === 'walkthrough')
  return {
    owner: me.role === 'admin',
    known: {
      consent: walkthrough?.open === false,
      residence: !residence.country,
      safety: readiness.due,
    },
    answeredAt: readiness.answered_at,
    draft: { safety: {} },
  }
}

/**
 * /start, the walk-through (ADR-0092): one question per screen, Back on each, and a progress
 * line. Every answer is held here in memory, never in device storage, so a reload starts again;
 * nothing is saved to the plan until Save at the end. The screens the server already has an
 * answer for (consent, where you live, the health questions while current) are skipped. The
 * owner gets a try-out: every screen, and his plan never changes.
 */
export default function StartPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [trail, setTrail] = useState<string[]>(['welcome'])
  const [draft, setDraft] = useState<Draft | null>(null)
  const main = useRef<HTMLElement>(null)
  const moved = useRef(false)
  const told = useRef(false)
  // Once a walk-through: the server hears only that this version of the questions was answered.
  const tell = useCallback(() => {
    if (told.current) return null
    told.current = true
    return answeredReadiness(VERSION)
  }, [])
  const here = trail[trail.length - 1]

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
      .then((ready) => {
        if (!ready) return setLoaded({ status: 'signed-out' })
        setLoaded({ status: 'ready', ready })
        setDraft(ready.draft)
      })
      .catch(() => {
        if (!ctrl.signal.aborted) setLoaded({ status: 'error' })
      })
    return () => ctrl.abort()
  }, [])

  // Each new screen's heading takes the focus, so a screen reader starts there.
  useEffect(() => {
    if (!moved.current) return
    const heading = main.current?.querySelector<HTMLElement>('h1, h2')
    heading?.setAttribute('tabindex', '-1')
    heading?.focus()
  }, [here])

  const frame = (children: React.ReactNode) => (
    <div className="page">
      <header className="masthead">
        <a href="/" className="wordmark no-underline">
          Training Coach
        </a>
      </header>
      <main ref={main} className="flex flex-col gap-4">
        {children}
      </main>
    </div>
  )

  if (loaded.status === 'loading')
    return frame(
      <p className="status" role="status">
        Loading…
      </p>,
    )
  if (loaded.status === 'signed-out')
    return frame(<SignInCard text="Sign in to set up your plan." />)
  if (loaded.status === 'error' || !draft)
    return frame(<RetryCard text="Couldn't load the walk-through. Check your connection." />)

  const { owner, known, answeredAt } = loaded.ready
  const go = (next: Draft = draft) => {
    const to = after(here, known, next)
    setDraft(next)
    moved.current = true
    if (to) setTrail([...trail, to])
  }
  const back = () => {
    moved.current = true
    setTrail(trail.slice(0, -1))
  }
  const n = numberOf(here)
  const safety = SAFETY.indexOf(here)

  return frame(
    <>
      {owner && (
        <p className={`${card} m-0 font-bold`} role="note">
          This is a try-out: your plan won't change.
        </p>
      )}
      {n > 0 && n <= LAST && (
        <p className="m-0 text-sm text-[var(--slate)]">
          {n} of {LAST}
        </p>
      )}
      {!known.safety && answeredAt && here === after('residence', known, draft) && (
        <p className="m-0 text-[var(--slate)]">
          You answered the health questions on {day(answeredAt)}.
        </p>
      )}
      {here === 'welcome' && <Welcome onStart={() => go()} />}
      {here === 'consent' && (
        <ConsentCard category="walkthrough" onGiven={() => go()} onNotNow={() => go()} />
      )}
      {here === 'residence' && (
        <>
          <Residence />
          <button type="button" className={primary} onClick={() => go()}>
            Next
          </button>
        </>
      )}
      {safety >= 0 && (
        <SafetyQuestion
          index={safety}
          value={draft.safety[QUESTIONS[safety].key]}
          onAnswer={(answer) =>
            go({ ...draft, safety: { ...draft.safety, [QUESTIONS[safety].key]: answer } })
          }
          onSkip={() => {
            // Not told to the server, so the app asks them again next time it opens.
            const to = after('safety-note', known, draft)
            moved.current = true
            if (to) setTrail([...trail, to])
          }}
        />
      )}
      {here === 'safety-note' && (
        <SafetyNote answers={draft.safety} tell={tell} onNext={() => go()} />
      )}
      {here === 'next' && (
        <>
          <h1 className="m-0 text-2xl">Next: about you</h1>
          <p className="m-0">
            The questions about you and what you can do come in the next version. Nothing was saved.
          </p>
        </>
      )}
      {trail.length > 1 && (
        <button type="button" className={`${secondary} self-start`} onClick={back}>
          Back
        </button>
      )}
    </>,
  )
}
