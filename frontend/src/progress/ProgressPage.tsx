import { useEffect, useState } from 'react'
import { fetchProgress, type Standing } from '../api'
import AppShell from '../components/AppShell'
import BandSummary from '../components/BandSummary'
import BodyFatTrend from './BodyFatTrend'
import SessionTimes from './SessionTimes'
import TrendChart from './TrendChart'
import { local } from './chart'
import { amount } from './logic'
import { card, secondary } from '../ui'
import { RetryCard, SignInCard } from '../components/StateCards'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; standings: Standing[]; today: Date }

const STATUS: Record<Standing['status'], string | null> = {
  ready: 'Ready to move up',
  top_of_ladder: 'Top of the ladder',
  hold: null,
}

/** /progress: each exercise's step and trend, and session times. The plan has its own page
 * now (/plan, ADR-0069). */
export default function ProgressPage() {
  return (
    <AppShell>
      <h1 className="text-3xl font-extrabold">Progress</h1>
      <Standings />
    </AppShell>
  )
}

/** Every exercise's step, last session, best set and six weeks of trend (as /progress in the
 * bot, which has no graph). Moving up stays with the prompt after a saved session. */
function Standings() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })

  useEffect(() => {
    fetchProgress()
      .then((found) =>
        setLoaded(
          found === null
            ? { status: 'signed-out' }
            : { status: 'ready', standings: found.standings, today: local(found.today) },
        ),
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
      <BandSummary />
      <BodyFatTrend />
      <SessionTimes />
      <ul className="flex flex-col gap-3">
        {loaded.standings.map((s) => {
          const status = STATUS[s.status]
          return (
            <li key={s.exercise} className={card + ' flex flex-col gap-3'}>
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
              <TrendChart standing={s} today={loaded.today} />
            </li>
          )
        })}
      </ul>
    </>
  )
}
