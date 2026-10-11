import { useEffect, useState } from 'react'
import {
  fetchCardio,
  logCardio,
  SignedOutError,
  type CardioActivity,
  type CardioKind,
  type CardioLogged,
  type CardioOptions,
} from '../api'
import HiitTimer from '../hiit/HiitTimer'
import SignedOutNotice from '../components/SignedOutNotice'
import { actions, card, primary, primaryInline, secondary } from '../ui'

const EFFORTS: { kind: CardioKind; label: string }[] = [
  { kind: 'zone2', label: 'Easy (zone 2)' },
  { kind: 'moderate-cardio', label: 'Harder (moderate)' },
]

const ACTIVITY: Record<CardioActivity, string> = {
  walk: 'Walk',
  hike: 'Hike',
  jog: 'Jog',
  run: 'Run',
  bike: 'Bike',
  swim: 'Swim',
  row: 'Row',
  stairs: 'Stairs',
  other: 'Other',
}

type Mode = 'menu' | 'log' | 'hiit' | 'rounds' | 'saved'

/** A fresh token per log: saving the same one twice saves once. */
function newToken(): string {
  return crypto.randomUUID().replaceAll('-', '')
}

const chip = (on: boolean) =>
  'min-h-11 rounded-full border-2 px-4 font-bold ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

/**
 * Cardio in one step (ux-flow-plan A1-A3): log the minutes and what it was, one tap for
 * "done as planned", or time HIIT intervals and save the rounds. ``featured`` when today's
 * planned session is this cardio: it then stands in for the session's Start button.
 */
export default function Cardio({ featured }: { featured: boolean }) {
  const [options, setOptions] = useState<CardioOptions | null>(null)
  const [fetched, setFetched] = useState(false)
  const [mode, setMode] = useState<Mode>('menu')
  const [kind, setKind] = useState<CardioKind>('zone2')
  const [activity, setActivity] = useState<CardioActivity | null>(null)
  const [value, setValue] = useState(30)
  const [token, setToken] = useState(newToken)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)
  const [logged, setLogged] = useState<CardioLogged | null>(null)

  useEffect(() => {
    const abort = new AbortController()
    fetchCardio(abort.signal)
      .then((found) => found && setOptions(found))
      .catch(() => {}) // the buttons still work without today's plan
      .finally(() => setFetched(true))
    return () => abort.abort()
  }, [])

  const planned = options?.planned ?? null
  const activities = options?.activities ?? (Object.keys(ACTIVITY) as CardioActivity[])

  /** Open a form with its starting values and nothing picked. */
  const open = (next: Mode, nextKind: CardioKind, nextValue: number) => {
    setNote(null)
    setKind(nextKind)
    setValue(nextValue)
    setActivity(null)
    setMode(next)
  }
  const logForm = () =>
    planned && planned.kind !== 'hiit'
      ? open('log', planned.kind, planned.target)
      : open('log', 'zone2', 30)

  /** The token stays until a save succeeds: a double tap or a retry after a lost answer
   * sends the same one, so it saves once. */
  const save = async (
    saveKind: CardioKind,
    saveValue: number,
    saveActivity: CardioActivity | null,
  ) => {
    if (busy) return
    setNote(null)
    setSignedOut(false)
    setBusy(true)
    try {
      const result = await logCardio({
        token,
        kind: saveKind,
        value: saveValue,
        activity: saveActivity,
      })
      if (result === 'stale') {
        setNote("Today's session changed (a rest, swap or another log), so this wasn't saved.")
        return
      }
      setToken(newToken())
      setKind(saveKind)
      setValue(saveValue)
      setActivity(saveActivity)
      setLogged(result)
      setMode('saved')
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't save. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  const feedback = (
    <>
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}
      {signedOut && <SignedOutNotice />}
    </>
  )

  if (mode === 'hiit')
    return (
      <section aria-label="HIIT timer" className="flex flex-col gap-4">
        <HiitTimer
          defaults={planned?.kind === 'hiit' ? { rounds: planned.target } : undefined}
          onFinish={(result) => open('rounds', 'hiit', result.rounds)}
          onCancel={() => setMode('menu')}
        />
      </section>
    )

  if (mode === 'rounds')
    return (
      <section aria-labelledby="rounds" className={`${card} flex flex-col gap-4`}>
        {feedback}
        <h2 id="rounds" className="text-2xl font-extrabold">
          Save your HIIT
        </h2>
        <Amount label="Rounds" value={value} steps={[1]} max={100} onChange={setValue} />
        <button
          type="button"
          className={primary}
          disabled={busy}
          onClick={() => save('hiit', value, null)}
        >
          Save {value} rounds
        </button>
        <button type="button" className={secondary} onClick={() => setMode('menu')}>
          Don't save
        </button>
      </section>
    )

  if (mode === 'log')
    return (
      <section aria-labelledby="log-cardio" className={`${card} flex flex-col gap-4`}>
        {feedback}
        <h2 id="log-cardio" className="text-2xl font-extrabold">
          Log cardio
        </h2>
        <fieldset className="flex flex-col gap-2 border-0 p-0">
          <legend className="mb-2 font-bold">How hard</legend>
          <div className="grid grid-cols-2 gap-2">
            {EFFORTS.map((effort) => (
              <button
                key={effort.kind}
                type="button"
                aria-pressed={kind === effort.kind}
                className={chip(kind === effort.kind)}
                onClick={() => setKind(effort.kind)}
              >
                {effort.label}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset className="flex flex-col gap-2 border-0 p-0">
          <legend className="mb-2 font-bold">What it was</legend>
          <div className={actions}>
            {activities.map((a) => (
              <button
                key={a}
                type="button"
                aria-pressed={activity === a}
                className={chip(activity === a)}
                onClick={() => setActivity(activity === a ? null : a)}
              >
                {ACTIVITY[a]}
              </button>
            ))}
          </div>
        </fieldset>
        <Amount label="Minutes" value={value} steps={[5, 1]} max={600} onChange={setValue} />
        <button
          type="button"
          className={primary}
          disabled={busy || value < 1}
          onClick={() => save(kind, value, activity)}
        >
          Save {value} min
        </button>
        <button type="button" className={secondary} onClick={() => setMode('menu')}>
          Cancel
        </button>
      </section>
    )

  if (mode === 'saved' && logged)
    return (
      <section aria-labelledby="cardio-saved" className={`${card} flex flex-col gap-3`}>
        <p className="m-0 font-bold">Saved</p>
        <h2 id="cardio-saved" className="text-3xl font-extrabold">
          {logged.planned && planned ? `${planned.session} done` : 'Logged'}
        </h2>
        <p className="m-0">
          {kind === 'hiit'
            ? `${value} HIIT rounds`
            : `${value} min${activity ? ` ${ACTIVITY[activity].toLowerCase()}` : ''}, ${kind === 'zone2' ? 'zone 2' : 'moderate'}`}
          {logged.already_saved ? ' (already saved)' : ''}.
        </p>
        <WeekBar week={logged.week} />
        {logged.planned && logged.next_session && (
          <p className="m-0">Next up: {logged.next_session}.</p>
        )}
        <div className={actions}>
          <a href="/" className={`${primaryInline} inline-flex items-center no-underline`}>
            Home
          </a>
          <a href="/progress" className={`${secondary} inline-flex items-center no-underline`}>
            See my progress
          </a>
          <button type="button" className={secondary} onClick={() => setMode('menu')}>
            Log more
          </button>
        </div>
      </section>
    )

  // The menu: today's planned cardio up front, or a card under any other session.
  if (featured && !fetched)
    return (
      <p className="status" role="status">
        Loading today's cardio…
      </p>
    )
  if (featured && planned)
    return (
      <section aria-labelledby="cardio-today" className="flex flex-col gap-4">
        {feedback}
        <p className="m-0 text-sm text-[var(--slate)]">Today</p>
        <h1 id="cardio-today" className="text-5xl font-extrabold">
          {planned.session}
        </h1>
        <p className="m-0 text-[var(--slate)]">
          Target {planned.target} {planned.kind === 'hiit' ? 'rounds' : 'min'}
        </p>
        {options && <WeekBar week={options.week} />}
        {planned.kind === 'hiit' ? (
          <>
            <button type="button" className={primary} onClick={() => setMode('hiit')}>
              Start HIIT timer
            </button>
            <button
              type="button"
              className={secondary}
              onClick={() => open('rounds', 'hiit', planned.target)}
            >
              Log rounds without the timer
            </button>
            <button type="button" className={secondary} onClick={logForm}>
              Log other cardio
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className={primary}
              disabled={busy}
              onClick={() => save(planned.kind, planned.target, null)}
            >
              Done as planned: {planned.target} min
            </button>
            <button type="button" className={secondary} onClick={logForm}>
              Log different minutes or activity
            </button>
            <button type="button" className={secondary} onClick={() => setMode('hiit')}>
              Run a HIIT session
            </button>
          </>
        )}
      </section>
    )

  return (
    <section aria-labelledby="cardio" className={`${card} flex flex-col gap-3`}>
      {feedback}
      <h2 id="cardio" className="text-lg font-bold">
        Cardio or HIIT
      </h2>
      <p className="m-0 text-[var(--slate)]">Log a walk, ride or run, or time some intervals.</p>
      <div className={actions}>
        <button type="button" className={primaryInline} onClick={logForm}>
          Log cardio
        </button>
        <button type="button" className={secondary} onClick={() => setMode('hiit')}>
          Run a HIIT session
        </button>
      </div>
    </section>
  )
}

/** A number typed or nudged with buttons, kept between 1 and ``max``. */
function Amount({
  label,
  value,
  steps,
  max,
  onChange,
}: {
  label: string
  value: number
  steps: number[]
  max: number
  onChange: (value: number) => void
}) {
  const set = (v: number) => onChange(Math.min(max, Math.max(1, Math.round(v))))
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={`amount-${label}`} className="font-bold">
        {label}
      </label>
      <div className="flex items-center justify-center gap-2">
        {steps.map((s) => (
          <button
            key={`-${s}`}
            type="button"
            aria-label={`${s} fewer`}
            className="size-12 rounded-full border-2 border-[var(--ink)] font-bold"
            onClick={() => set(value - s)}
          >
            −{s}
          </button>
        ))}
        <input
          id={`amount-${label}`}
          type="number"
          inputMode="numeric"
          min={1}
          max={max}
          value={value}
          onChange={(e) => set(Number(e.target.value) || 1)}
          className="w-24 text-center text-3xl font-extrabold"
        />
        {[...steps].reverse().map((s) => (
          <button
            key={`+${s}`}
            type="button"
            aria-label={`${s} more`}
            className="size-12 rounded-full border-2 border-[var(--ink)] font-bold"
            onClick={() => set(value + s)}
          >
            +{s}
          </button>
        ))}
      </div>
    </div>
  )
}

/** This week's zone 2 minutes against the plan's target. */
function WeekBar({ week }: { week: CardioOptions['week'] }) {
  const target = week.zone2_target
  return (
    <div className="flex flex-col gap-1">
      <p className="m-0 text-sm">
        This week: <span className="font-bold">{week.zone2}</span>
        {target ? ` of ${target[0]}–${target[1]}` : ''} zone 2 min
        {week.moderate > 0 ? `, ${week.moderate} moderate` : ''}
      </p>
      {target && (
        <div
          role="meter"
          aria-label="Zone 2 this week"
          aria-valuemin={0}
          aria-valuemax={target[0]}
          aria-valuenow={Math.min(week.zone2, target[0])}
          className="h-3 overflow-hidden rounded-full bg-[var(--line)]"
        >
          <div
            className="h-full bg-[var(--bell)]"
            style={{ width: `${Math.min(100, Math.round((week.zone2 / target[0]) * 100))}%` }}
          />
        </div>
      )}
    </div>
  )
}
