import { useEffect, useState } from 'react'
import { fetchProgress, type Standing } from '../api'
import AppShell from '../components/AppShell'
import BandSummary from '../components/BandSummary'
import BodyFatTrend from './BodyFatTrend'
import SessionTimes from './SessionTimes'
import TrendChart from './TrendChart'
import { local } from './chart'
import { lastAndBest } from './logic'
import { KIT_HREF } from '../account/kit'
import { moveButton, moveHref, needs, topLabel } from '../plan/ladder'
import { card, secondary } from '../ui'
import { RetryCard, SignInCard } from '../components/StateCards'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; standings: Standing[]; today: Date }

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
 * bot, which has no graph). "Ready to move up" links to that ladder on /plan (ADR-0075). */
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

  const ready = loaded.standings.filter((s) => s.status === 'ready')
  return (
    <>
      <p className="m-0 text-[var(--slate)]">
        Each exercise's current step, its last session and best set there.
        {ready.length > 0 && (
          <>
            {' '}
            <a
              href={moveHref(ready[0].slug)}
              className="font-bold text-[var(--bell-ink)] underline"
            >
              {ready.length} ready to move up
            </a>
            : choose on the Plan page, or when you're asked after your next session.
          </>
        )}
      </p>
      <a href="/review" className={secondary + ' inline-flex items-center self-start no-underline'}>
        This week's review
      </a>
      <BandSummary />
      <BodyFatTrend />
      <SessionTimes />
      <ul className="flex flex-col gap-3">
        {loaded.standings.map((s) => {
          const status = s.status === 'ready' ? 'Ready to move up' : topLabel(s)
          const here = s.ladder.find((r) => r.id === s.step_id)
          const locked = here ? needs(here) : null
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
                <span>{lastAndBest(s)}</span>
                {s.status === 'ready' ? (
                  <a href={moveHref(s.slug)} className={moveButton}>
                    {status}
                  </a>
                ) : (
                  status && <span className="font-bold text-[var(--bell-ink)]">{status}</span>
                )}
                {s.unlock && (
                  <span>
                    {s.unlock[0].toUpperCase() + s.unlock.slice(1)}.{' '}
                    <a href={KIT_HREF} className="font-bold underline">
                      My equipment
                    </a>
                  </span>
                )}
                {locked && <span>This step {locked}, not in your kit.</span>}
              </div>
              <TrendChart standing={s} today={loaded.today} />
            </li>
          )
        })}
      </ul>
    </>
  )
}
