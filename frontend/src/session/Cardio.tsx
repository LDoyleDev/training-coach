import { useEffect, useRef, useState } from 'react'
import {
  fetchCardio,
  logCardio,
  RefusedError,
  SignedOutError,
  type CardioActivity,
  type CardioKind,
  type CardioLog,
  type CardioLogged,
  type CardioOptions,
} from '../api'
import HiitTimer from '../hiit/HiitTimer'
import { DEFAULT_SOUND, type Sound, playSessionEnd, unlockAudio } from '../hiit/sounds'
import SignedOutNotice from '../components/SignedOutNotice'
import CardioWeek from './CardioWeek'
import Undo from './Undo'
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

/** What a log can carry besides its minutes (ADR-0067), each only when given. */
type Details = Pick<CardioLog, 'effort' | 'distance_km' | 'avg_hr' | 'max_hr' | 'start'>

/** Seconds per km as "5:54". */
function paceText(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

/** "24.3 km/h": a ride is read by its speed, not its pace. */
const speedText = (minutes: number, km: number) => `${((km * 60) / minutes).toFixed(1)} km/h`

/** A typed number, or null when the box is empty or not a number. */
const typed = (text: string): number | null => {
  const n = Number(text.replace(',', '.'))
  return text.trim() === '' || !Number.isFinite(n) ? null : n
}

/** The saved log in words: "effort 6/10 · 7.29 km · 5:54 /km · HR 139 avg, 160 max"; a ride
 * (``rideMinutes``) shows its speed instead of the pace. */
function detailsText(
  details: Details,
  pace: number | null | undefined,
  rideMinutes: number | null,
): string {
  const speed = rideMinutes && details.distance_km && speedText(rideMinutes, details.distance_km)
  const parts = [
    details.effort ? `effort ${details.effort}/10` : null,
    details.distance_km ? `${details.distance_km} km` : null,
    speed || (pace ? `${paceText(pace)} /km` : null),
    details.avg_hr || details.max_hr
      ? `HR ${[details.avg_hr && `${details.avg_hr} avg`, details.max_hr && `${details.max_hr} max`]
          .filter(Boolean)
          .join(', ')}`
      : null,
  ]
  return parts.filter(Boolean).join(' · ')
}

/** A fresh token per log: saving the same one twice saves once. */
function newToken(): string {
  return crypto.randomUUID().replaceAll('-', '')
}

const chip = (on: boolean) =>
  'min-h-11 rounded-full border-2 px-4 font-bold ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

/** What the page hears: the saved screen opened or closed, or the log was undone. */
export type CardioChange = 'saved' | 'closed' | 'undone'

/**
 * Cardio in one step (ux-flow-plan A1-A3): log the minutes and what it was, one tap for
 * "done as planned", or time HIIT intervals and save the rounds. ``featured`` when today's
 * planned session is this cardio: it then stands in for the session's Start button. The saved
 * screen offers Undo (C3). A save rings the end of the session in the person's timer sound,
 * unless the HIIT timer rang it at its end.
 */
export default function Cardio({
  featured,
  onChange,
  sound = DEFAULT_SOUND,
}: {
  featured: boolean
  onChange?: (change: CardioChange) => void
  sound?: Sound
}) {
  const [options, setOptions] = useState<CardioOptions | null>(null)
  const [fetched, setFetched] = useState(false)
  const [mode, setMode] = useState<Mode>('menu')
  const [kind, setKind] = useState<CardioKind>('zone2')
  const [activity, setActivity] = useState<CardioActivity | null>(null)
  const [value, setValue] = useState(30)
  const [effort, setEffort] = useState<number | null>(null)
  const [distance, setDistance] = useState('')
  const [avgHr, setAvgHr] = useState('')
  const [maxHr, setMaxHr] = useState('')
  const [start, setStart] = useState('')
  const [saved, setSaved] = useState<Details>({})
  // The token and the log it was first sent with: only that same log, retried, reuses it.
  const sent = useRef<{ token: string; log: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)
  const [logged, setLogged] = useState<CardioLogged | null>(null)
  // The HIIT timer ran to its end and rang the end of the session: saving its rounds doesn't.
  const rang = useRef(false)

  const [loads, setLoads] = useState(0) // again after an undo: today's plan is back
  useEffect(() => {
    const abort = new AbortController()
    fetchCardio(abort.signal)
      .then((found) => found && setOptions(found))
      .catch(() => {}) // the buttons still work without today's plan
      .finally(() => setFetched(true))
    return () => abort.abort()
  }, [loads])

  const planned = options?.planned ?? null
  const activities = options?.activities ?? (Object.keys(ACTIVITY) as CardioActivity[])

  /** Open a form with its starting values and nothing picked. */
  const open = (next: Mode, nextKind: CardioKind, nextValue: number) => {
    rang.current = false
    setNote(null)
    setKind(nextKind)
    setValue(nextValue)
    setActivity(null)
    setEffort(null)
    setDistance('')
    setAvgHr('')
    setMaxHr('')
    setStart('')
    setMode(next)
  }
  const logForm = () =>
    planned && planned.kind !== 'hiit'
      ? open('log', planned.kind, planned.target)
      : open('log', 'zone2', 30)

  /** A double tap, or a retry after a lost answer, sends the same log with the same token, so
   * it saves once; a different log always gets a new token. */
  const save = async (
    saveKind: CardioKind,
    saveValue: number,
    saveActivity: CardioActivity | null,
    details: Details = {},
  ) => {
    if (busy) return
    unlockAudio() // inside the tap: browsers only allow sound after a gesture
    const log = JSON.stringify([saveKind, saveValue, saveActivity, details])
    if (sent.current?.log !== log) sent.current = { token: newToken(), log }
    const token = sent.current.token
    setNote(null)
    setSignedOut(false)
    setBusy(true)
    try {
      const result = await logCardio({
        token,
        kind: saveKind,
        value: saveValue,
        activity: saveActivity,
        ...details,
      })
      if (result === 'stale') {
        setNote("Today's session changed (a rest, swap or another log), so this wasn't saved.")
        return
      }
      sent.current = null
      if (!result.already_saved && !(saveKind === 'hiit' && rang.current)) playSessionEnd(sound)
      rang.current = false
      setKind(saveKind)
      setValue(saveValue)
      setActivity(saveActivity)
      setSaved(details)
      setLogged(result)
      setMode('saved')
      onChange?.('saved')
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else if (error instanceof RefusedError) setNote(`Not saved: ${error.message}.`)
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
          sound={sound}
          onFinish={(result) => {
            open('rounds', 'hiit', result.rounds)
            rang.current = !result.early
          }}
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
        <fieldset className="flex flex-col gap-2 border-0 p-0">
          <legend className="mb-2 font-bold">How it felt, 1 (very easy) to 10 (all out)</legend>
          <div className="grid grid-cols-5 gap-2">
            {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                type="button"
                aria-pressed={effort === n}
                aria-label={`Effort ${n}`}
                className={chip(effort === n)}
                onClick={() => setEffort(n)}
              >
                {n}
              </button>
            ))}
          </div>
        </fieldset>
        <details className="flex flex-col gap-2">
          <summary className="min-h-11 cursor-pointer font-bold">
            More from your watch or app (optional)
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-3">
            <Detail label="Distance (km)" value={distance} decimal onChange={setDistance} />
            <label className="flex flex-col gap-1 font-bold">
              Started at
              <input
                type="time"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="min-h-11 text-lg"
              />
            </label>
            <Detail label="Average heart rate" value={avgHr} onChange={setAvgHr} />
            <Detail label="Highest heart rate" value={maxHr} onChange={setMaxHr} />
          </div>
          {typed(distance) && value > 0 ? (
            <p className="m-0 mt-2" role="status">
              {activity === 'bike'
                ? `Speed ${speedText(value, typed(distance) ?? 1)}`
                : `Pace ${paceText(Math.round((value * 60) / (typed(distance) ?? 1)))} /km`}
            </p>
          ) : null}
        </details>
        <button
          type="button"
          className={primary}
          disabled={busy || value < 1 || effort === null}
          onClick={() =>
            save(kind, value, activity, {
              effort,
              distance_km: typed(distance),
              avg_hr: typed(avgHr),
              max_hr: typed(maxHr),
              start: start || null,
            })
          }
        >
          {effort === null ? 'Pick how it felt to save' : `Save ${value} min`}
        </button>
        <button type="button" className={secondary} onClick={() => setMode('menu')}>
          Cancel
        </button>
      </section>
    )

  const ride = activity === 'bike' ? value : null
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
        {detailsText(saved, logged.pace, ride) && (
          <p className="m-0 text-[var(--slate)]">{detailsText(saved, logged.pace, ride)}</p>
        )}
        <CardioWeek week={logged.week} />
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
          <button
            type="button"
            className={secondary}
            onClick={() => {
              setMode('menu')
              onChange?.('closed')
            }}
          >
            Log more
          </button>
        </div>
        <Undo
          onUndone={(done) => {
            setNote(`Undone: ${done.what}.`)
            setLogged(null)
            setMode('menu')
            setLoads((n) => n + 1)
            onChange?.('undone')
          }}
        />
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
        {options && <CardioWeek week={options.week} />}
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

/** One optional number from a watch or app; empty means not given. */
function Detail({
  label,
  value,
  decimal = false,
  onChange,
}: {
  label: string
  value: string
  decimal?: boolean
  onChange: (value: string) => void
}) {
  return (
    <label className="flex flex-col gap-1 font-bold">
      {label}
      <input
        type="text"
        inputMode={decimal ? 'decimal' : 'numeric'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-11 text-lg"
      />
    </label>
  )
}
