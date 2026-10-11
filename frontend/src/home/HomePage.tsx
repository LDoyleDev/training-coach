import { useEffect, useState } from 'react'
import { fetchHome, type Home } from '../api'
import AppShell from '../components/AppShell'
import { RetryCard, SignInCard } from '../components/StateCards'
import { InstallHint } from '../pwa/InstallApp'
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

/** /: the first screen (B1). What you've done, to motivate; the week and the ladders as a
 * summary; then the button to today's session. */
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
  const target = week.zone2_target?.[0] ?? null
  const zone2 = target ? Math.min(100, Math.round((week.zone2_minutes / target) * 100)) : 0
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
          <p className="m-0 font-bold text-[var(--bell-ink)]">
            Ready to move up: {progress.ready.join(', ')}
          </p>
        )}
        {progress.bests.length > 0 && (
          <p className="m-0">Personal bests this week: {progress.bests.join(', ')}</p>
        )}
      </section>

      <section aria-labelledby="week" className={card + ' flex flex-col gap-2'}>
        <h2 id="week" className="m-0 text-xl font-bold">
          This week
        </h2>
        <p className="m-0">
          {week.done} of {week.planned} sessions done
          {week.extras > 0 && ` · ${week.extras} extra`}
        </p>
        <div className="flex flex-col gap-1">
          <span>
            Zone 2: {week.zone2_minutes}
            {week.zone2_target && ` of ${week.zone2_target[0]}–${week.zone2_target[1]}`} min
          </span>
          {target !== null && (
            <div
              role="meter"
              aria-label="Zone 2 minutes this week"
              aria-valuemin={0}
              aria-valuemax={target}
              aria-valuenow={Math.min(week.zone2_minutes, target)}
              className="h-3 overflow-hidden rounded-full bg-[var(--line)]"
            >
              <div className="h-full bg-[var(--bell)]" style={{ width: `${zone2}%` }} />
            </div>
          )}
        </div>
        <h3 className="m-0 mt-2 text-base font-bold">Last 7 days</h3>
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
          <p className="m-0 text-[var(--slate)]">Nothing logged in the last seven days.</p>
        )}
      </section>

      <InstallHint />

      <a href="/session" className={primary + ' flex items-center justify-center no-underline'}>
        {today ? `Today: ${today}` : 'Go to today'}
      </a>
      <div className="grid grid-cols-2 gap-2">
        <a
          href="/progress"
          className={secondary + ' flex items-center justify-center no-underline'}
        >
          Progress
        </a>
        <a
          href="/progress?tab=plan"
          className={secondary + ' flex items-center justify-center no-underline'}
        >
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
