import { useEffect, useState } from 'react'
import { fetchHome, type Home } from '../api'
import AppShell from '../components/AppShell'
import BandSummary from '../components/BandSummary'
import { RetryCard, SignInCard } from '../components/StateCards'
import { moveButton, moveHref } from '../plan/ladder'
import { InstallHint } from '../pwa/InstallApp'
import { range, standing } from '../session/cardioTotals'
import { card, primary, secondary } from '../ui'
import { ago, day } from './logic'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; home: Home }

const count = (n: number) => n.toLocaleString('en-GB')

function Big({ value, label }: { value: number; label: string }) {
  return (
    <div className={card + ' flex flex-col'}>
      <span className="text-4xl font-extrabold tabular-nums">{count(value)}</span>
      <span className="text-[var(--slate)]">{label}</span>
    </div>
  )
}

/** /: the first screen (B1). What you've done, to motivate; the last 7 days and the ladders
 * as a summary; then the button to today's session. The last 7 days are a running total, not
 * the calendar week, so a Monday still shows the weekend (ADR-0077). */
export default function HomePage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })

  useEffect(() => {
    fetchHome()
      .then((home) =>
        setLoaded(home === null ? { status: 'signed-out' } : { status: 'ready', home }),
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
        <SignInCard text="Sign in to see your training." />
      </AppShell>
    )
  if (loaded.status === 'error')
    return (
      <AppShell>
        <RetryCard text="Couldn't load your training. Check your connection." />
      </AppShell>
    )

  const { totals, week, progress, recent, today } = loaded.home
  const usual = loaded.home.today_usual_minutes
  const about = loaded.home.today_minutes
  // how long it takes, to make starting easier: earlier timed sessions first (ADR-0061)
  const length = usual ? ` · usually ${usual} min` : about ? ` · about ${about} min` : ''
  // All cardio against its target, then what's left of each (ADR-0079).
  const target = week.cardio_target?.[0] ?? null
  const cardio = target ? Math.min(100, Math.round((week.cardio_minutes / target) * 100)) : 0
  const left = [standing(week.cardio_left), standing(week.zone2_left)]
  const where = [left[0] && `Cardio ${left[0]}`, left[1] && `zone 2 ${left[1]}`]
    .filter(Boolean)
    .join(' · ')
  return (
    <AppShell>
      <section aria-labelledby="done" className="flex flex-col gap-3">
        <h1 id="done" className="m-0 text-3xl font-extrabold">
          {totals.sessions > 0 ? "What you've done" : 'Your first session is waiting'}
        </h1>
        {totals.first_day && (
          <p className="m-0 text-[var(--slate)]">
            Training since {day(totals.first_day)}, {ago(totals.days)}.
          </p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Big value={totals.sessions} label="sessions" />
          <Big value={totals.sets} label="sets" />
          <Big value={totals.reps} label="reps" />
          <Big value={totals.cardio_minutes} label="cardio minutes" />
        </div>
      </section>

      <section aria-labelledby="ladders" className={card + ' flex flex-col gap-1'}>
        <h2 id="ladders" className="m-0 text-xl font-bold">
          Progress
        </h2>
        <p className="m-0">
          <span className="text-2xl font-extrabold tabular-nums">{progress.steps_climbed}</span>{' '}
          {progress.steps_climbed === 1 ? 'ladder step' : 'ladder steps'} climbed
        </p>
        {progress.ready.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="m-0 font-bold text-[var(--bell-ink)]">Ready to move up:</p>
            <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
              {progress.ready.map((r) => (
                <li key={r.slug}>
                  <a href={moveHref(r.slug)} className={moveButton}>
                    {r.exercise}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
        {progress.bests.length > 0 && (
          <p className="m-0">Personal bests in the last 7 days: {progress.bests.join(', ')}</p>
        )}
      </section>

      <section aria-labelledby="week" className={card + ' flex flex-col gap-2'}>
        <h2 id="week" className="m-0 text-xl font-bold">
          Last 7 days
        </h2>
        <p className="m-0">
          {week.done} of {week.planned} sessions done
          {week.extras > 0 && ` · ${week.extras} extra`}
        </p>
        <div className="flex flex-col gap-1">
          <span>
            Cardio {week.cardio_minutes}
            {range(week.cardio_target)} min · zone 2 {week.zone2_minutes}
            {range(week.zone2_target)}
          </span>
          {where && <span className="text-sm text-[var(--slate)]">{where}</span>}
          {target !== null && (
            <div
              role="meter"
              aria-label="Cardio minutes in the last 7 days"
              aria-valuemin={0}
              aria-valuemax={target}
              aria-valuenow={Math.min(week.cardio_minutes, target)}
              className="h-3 overflow-hidden rounded-full bg-[var(--line)]"
            >
              <div className="h-full bg-[var(--bell)]" style={{ width: `${cardio}%` }} />
            </div>
          )}
        </div>
        <h3 className="m-0 mt-2 text-base font-bold">Day by day</h3>
        {recent.length > 0 ? (
          <ul className="m-0 flex list-none flex-col gap-1 p-0">
            {recent.map((r, i) => (
              <li key={`${r.day}-${i}`} className="flex justify-between gap-3">
                <span>{r.session}</span>
                <span className="text-[var(--slate)]">{day(r.day)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="m-0 text-[var(--slate)]">Nothing logged in the last 7 days.</p>
        )}
      </section>

      <BandSummary />

      <InstallHint />

      <a href="/session" className={primary + ' flex items-center justify-center no-underline'}>
        {today ? `Today: ${today}${length}` : 'Go to today'}
      </a>
      <div className="grid grid-cols-2 gap-2">
        <a
          href="/progress"
          className={secondary + ' flex items-center justify-center no-underline'}
        >
          Progress
        </a>
        <a href="/plan" className={secondary + ' flex items-center justify-center no-underline'}>
          Plan
        </a>
        <a
          href="/review"
          className={secondary + ' col-span-2 flex items-center justify-center no-underline'}
        >
          This week's review
        </a>
      </div>
    </AppShell>
  )
}
