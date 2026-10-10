import { useEffect, useState } from 'react'
import { fetchProgress, type Standing } from '../api'
import AppShell from '../components/AppShell'
import { amount, trend } from './logic'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; standings: Standing[] }

const card = 'rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4'

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
        <p className="status">
          Sign in to see your progress. <a href="/signin">Sign in</a>
        </p>
      </AppShell>
    )
  if (loaded.status === 'error')
    return (
      <AppShell>
        <p className="status status-error" role="alert">
          Couldn't load your progress. Check your connection and reload the page.
        </p>
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
          const points = trend(s.recent)
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
              {points && (
                <svg
                  width="120"
                  height="32"
                  viewBox="0 0 120 32"
                  role="img"
                  aria-label={`Best set, last ${s.recent.length} sessions`}
                  className="shrink-0"
                >
                  <polyline
                    points={points}
                    fill="none"
                    stroke="var(--bell-ink)"
                    strokeWidth="2"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </li>
          )
        })}
      </ul>
    </AppShell>
  )
}
