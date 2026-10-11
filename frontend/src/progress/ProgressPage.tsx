import { useEffect, useState } from 'react'
import { fetchProgress, type Standing } from '../api'
import PlanView from '../App'
import AppShell from '../components/AppShell'
import Sparkline from '../components/Sparkline'
import { amount } from './logic'
import { card, secondary } from '../ui'
import { RetryCard, SignInCard } from '../components/StateCards'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; standings: Standing[] }

type Tab = 'progress' | 'plan'

const STATUS: Record<Standing['status'], string | null> = {
  ready: 'Ready to move up',
  top_of_ladder: 'Top of the ladder',
  hold: null,
}

const TABS: [Tab, string][] = [
  ['progress', 'My progress'],
  ['plan', 'The plan'],
]

const tab =
  'min-h-11 flex-1 rounded-xl border-2 border-[var(--ink)] px-3 font-bold text-[var(--ink)] aria-selected:bg-[var(--ink)] aria-selected:text-[var(--chalk)]'

/** /progress: my progress, and the plan (ux-flow-plan D2: the Plan page lives here now; /plan
 * opens it as ?tab=plan). */
export default function ProgressPage() {
  const [shown, setShown] = useState<Tab>(() =>
    new URLSearchParams(window.location.search).get('tab') === 'plan' ? 'plan' : 'progress',
  )
  const show = (next: Tab) => {
    setShown(next)
    window.history.replaceState(null, '', next === 'plan' ? '/progress?tab=plan' : '/progress')
  }
  return (
    <AppShell>
      <h1 className="text-3xl font-extrabold">Progress</h1>
      <div role="tablist" aria-label="Progress" className="flex gap-2">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={shown === key}
            className={tab}
            onClick={() => show(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="flex flex-col gap-4">
        {shown === 'plan' ? <PlanView /> : <Standings />}
      </div>
    </AppShell>
  )
}

/** Every exercise's step, last session, best set and trend (as /progress in the bot). Moving
 * up stays with the prompt after a saved session. */
function Standings() {
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
      <p className="status" role="status">
        Loading…
      </p>
    )
  if (loaded.status === 'signed-out') return <SignInCard text="Sign in to see your progress." />
  if (loaded.status === 'error')
    return <RetryCard text="Couldn't load your progress. Check your connection." />

  const ready = loaded.standings.filter((s) => s.status === 'ready').length
  return (
    <>
      <p className="m-0 text-[var(--slate)]">
        Each exercise's current step, its last session and best set there.
        {ready > 0 && ` ${ready} ready to move up: you'll be asked after your next session.`}
      </p>
      <a href="/review" className={secondary + ' inline-flex items-center self-start no-underline'}>
        This week's review
      </a>
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
    </>
  )
}
