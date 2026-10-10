import { useEffect, useState } from 'react'
import { fetchProgress, type Standing } from '../api'
import AppShell from '../components/AppShell'
import Sparkline from '../components/Sparkline'
import { amount } from './logic'
import { card } from '../ui'
import { RetryCard, SignInCard } from '../components/StateCards'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; standings: Standing[] }

const STATUS: Record<Standing['status'], string | null> = {
  ready: 'Ready to move up',
  top_of_ladder: 'Top of the ladder',
  hold: null,
}

/** /progress: every exercise's step, last session, best set and trend (as /progress in the
 * bot). Moving up stays with the prompt after a saved session. */
export default function ProgressPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })

  useEffect(() => {
    fetchProgress()
      .then((standings) =>
        setLoaded(standings === null ? { status: 'signed-out' } : { status: 'ready', standings }),
      )
      .catch(() => setLoaded({ status: 'error' }))
  }, [])

  if (loaded.status === 'loading')
    return (
      <AppShell>
        <p className="status" role="status">
          Loading…
        </p>
      </AppShell>
    )
  if (loaded.status === 'signed-out')
    return (
      <AppShell>
        <SignInCard text="Sign in to see your progress." />
      </AppShell>
    )
  if (loaded.status === 'error')
    return (
      <AppShell>
        <RetryCard text="Couldn't load your progress. Check your connection." />
      </AppShell>
    )

  const ready = loaded.standings.filter((s) => s.status === 'ready').length
  return (
    <AppShell>
      <h1 className="text-3xl font-extrabold">Progress</h1>
      <p className="text-[var(--slate)]">
        Each exercise's current step, its last session and best set there.
        {ready > 0 && ` ${ready} ready to move up: you'll be asked after your next session.`}
      </p>
      <ul className="flex flex-col gap-3">
        {loaded.standings.map((s) => {
          const status = STATUS[s.status]
          return (
            <li key={s.exercise} className={card + ' flex items-center justify-between gap-3'}>
              <div className="flex flex-col gap-1">
                <span className="font-bold">
                  {s.exercise}
                  {s.retired && <span className="text-[var(--slate)]"> (retired)</span>}
                </span>
                <span className="text-[var(--slate)]">
                  {s.step} · step {s.step_number} of {s.steps}
                </span>
                <span>
                  {s.last.length > 0
                    ? `Last ${s.last.map((v) => amount(s, v)).join(' · ')}`
                    : 'Not logged at this step yet'}
                  {s.best_set !== null && ` · best ${amount(s, s.best_set)}`}
                </span>
                {status && <span className="font-bold text-[var(--bell-ink)]">{status}</span>}
              </div>
              <Sparkline values={s.recent} label={`Best set, last ${s.recent.length} sessions`} />
            </li>
          )
        })}
      </ul>
    </AppShell>
  )
}
