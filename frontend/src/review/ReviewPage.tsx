import { type ReactNode, useEffect, useState } from 'react'
import { fetchReview, type WeekReview } from '../api'
import AppShell from '../components/AppShell'
import { RetryCard, SignInCard } from '../components/StateCards'
import { moveButton, moveHref } from '../plan/ladder'
import { TopList } from '../plan/TopNotes'
import { kgText } from '../session/logic'
import { card, secondary } from '../ui'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; review: WeekReview }

type Best = WeekReview['bests'][number]

const link = secondary + ' inline-flex items-center no-underline'

function day(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function amount(value: number, kind: Best['kind']): string {
  if (kind === 'seconds') return `${value} s`
  if (kind === 'duration_min') return `${value} min`
  return `${value} rep${value === 1 ? '' : 's'}`
}

function best(b: Best): string {
  const parts = []
  if (b.best_set !== null) parts.push(`${amount(b.best_set, b.kind)} in one set`)
  if (b.total !== null) parts.push(`${amount(b.total, b.kind)} in total`)
  return parts.join(' and ')
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={card + ' flex flex-col gap-2'}>
      <h2 className="m-0 text-lg font-bold">{title}</h2>
      {children}
    </section>
  )
}

/** /review: the weekly review the bot sends on Sundays (ux-flow-plan C4), this week so far by
 * default, with earlier weeks a tap away. */
export default function ReviewPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const week = new URLSearchParams(window.location.search).get('week') ?? undefined

  useEffect(() => {
    const controller = new AbortController()
    fetchReview(week, controller.signal)
      .then((review) =>
        setLoaded(review === null ? { status: 'signed-out' } : { status: 'ready', review }),
      )
      .catch(() => controller.signal.aborted || setLoaded({ status: 'error' }))
    return () => controller.abort()
  }, [week])

  if (loaded.status !== 'ready')
    return (
      <AppShell>
        {loaded.status === 'loading' && (
          <p className="status" role="status">
            Loading…
          </p>
        )}
        {loaded.status === 'signed-out' && <SignInCard text="Sign in to see your week." />}
        {loaded.status === 'error' && (
          <RetryCard text="Couldn't load the review. Check your connection." />
        )}
      </AppShell>
    )

  const r = loaded.review
  const [low, high] = r.sets_target
  const extras = [
    r.rested > 0 && `${r.rested} rest day${r.rested === 1 ? '' : 's'}`,
    r.extras > 0 && `${r.extras} extra`,
  ].filter(Boolean)
  const zone2 = r.zone2_target
    ? `${r.zone2_minutes} of ${r.zone2_target[0]}-${r.zone2_target[1]} min` +
      (r.zone2_minutes < r.zone2_target[0] ? ` (${r.zone2_target[0] - r.zone2_minutes} short)` : '')
    : `${r.zone2_minutes} min`

  return (
    <AppShell>
      <h1 className="text-3xl font-extrabold">
        {r.current ? 'This week' : `Week of ${day(r.start)}`}
      </h1>
      <p className="m-0 text-[var(--slate)]">
        {r.current ? `From ${day(r.start)}, so far.` : 'Monday to Sunday.'}
      </p>

      <Section title="Sessions">
        <p className="m-0">
          {r.done} of {r.planned} done{extras.length > 0 && ` (${extras.join(', ')})`}.
        </p>
      </Section>

      <Section title={`Hard sets per muscle (aim ${low}-${high})`}>
        {r.sets.length === 0 ? (
          <p className="m-0 text-[var(--slate)]">No sets logged this week.</p>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-1 p-0">
            {r.sets.map(({ group, sets }) => (
              <li key={group} className="flex justify-between gap-3">
                <span>{group}</span>
                <span>
                  {sets}
                  {sets < low && ' (low)'}
                  {sets > high && ' (high)'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Cardio">
        <p className="m-0">Zone 2: {zone2}</p>
        <p className="m-0">Moderate: {r.moderate_minutes} min</p>
      </Section>

      {r.bests.length > 0 && (
        <Section title="New bests">
          <ul className="m-0 flex flex-col gap-1 pl-5">
            {r.bests.map((b) => (
              <li key={`${b.exercise}-${b.step}-${b.strength}`}>
                {b.exercise} ({b.step}
                {b.strength && ', strength block'}
                {b.load_kg !== null && `, at ${kgText(b.load_kg)}`}): {best(b)}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.ready.length > 0 && (
        <Section title="Ready to move up">
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {r.ready.map((x) => (
              <li key={x.slug}>
                <a href={moveHref(x.slug)} className={moveButton}>
                  {x.exercise}
                </a>
              </li>
            ))}
          </ul>
          <p className="m-0">
            {r.strength_block
              ? 'When the hypertrophy block starts.'
              : 'Choose on the Plan page, or when asked after your next session.'}
          </p>
        </Section>
      )}

      {r.top.length > 0 && (
        <Section title="At the top">
          <TopList top={r.top} />
        </Section>
      )}

      {r.habits.length > 0 && (
        <Section title="Habits">
          <ul className="m-0 flex list-none flex-col gap-1 p-0">
            {r.habits.map((h) => (
              <li key={h.label} className="flex justify-between gap-3">
                <span>{h.label}</span>
                <span>
                  {h.done} of {h.days}
                  {h.days < 7 && ' so far'}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.ai_comment ? (
        // Untrusted AI text (ADR-0056): rendered as plain text, never as HTML or markdown.
        <section className={card + ' flex flex-col gap-2'} aria-label="AI comment">
          <p className="m-0 text-sm font-semibold text-[var(--slate)]">
            AI comment (from your Groq key, a suggestion only)
          </p>
          <p className="m-0 break-words whitespace-pre-line">{r.ai_comment}</p>
        </section>
      ) : (
        r.ai_comments && (
          <p className="m-0 text-sm text-[var(--slate)]">
            The AI comment from your Groq key comes on Telegram with Sunday's review, and shows here
            for 7 days after.
          </p>
        )
      )}

      <nav aria-label="Other weeks" className="flex flex-wrap gap-2">
        <a href={`/review?week=${r.previous}`} className={link}>
          Week before
        </a>
        {r.next && (
          <a href={`/review?week=${r.next}`} className={link}>
            Week after
          </a>
        )}
        {!r.current && (
          <a href="/review" className={link}>
            This week
          </a>
        )}
      </nav>
    </AppShell>
  )
}
