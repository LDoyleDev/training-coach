import { useEffect, useState } from 'react'
import {
  deleteMeasurement,
  fetchBody,
  saveBody,
  SignedOutError,
  type BodyData,
  type Measurement,
} from '../api'
import { Frame } from '../components/AppShell'
import SignedOutNotice from '../components/SignedOutNotice'
import BodyFatChart from './BodyFatChart'
import { byDay, change, format, isoDay, latest, parse, type Latest } from './logic'
import Photos from './Photos'
import Sparkline from '../components/Sparkline'
import { card, primary, small } from '../ui'
import Toast from '../components/Toast'
import { RetryCard, SignInCard } from '../components/StateCards'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | ({ status: 'ready' } & BodyData)

/** /body: measurements (2-B, #142), how to take them and the trends (ADR-0076). Personal:
 * never in a share view. */
export default function BodyPage({ embedded = false }: { embedded?: boolean }) {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [typed, setTyped] = useState<Record<string, string>>({})
  const [day, setDay] = useState(() => isoDay(new Date()))
  const [bounds] = useState(() => ({ min: isoDay(new Date(), 14), max: isoDay(new Date()) }))
  const [note, setNote] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([]) // kept until the next save or dismissed
  const [busy, setBusy] = useState(false)
  const [signedOut, setSignedOut] = useState(false) // the sign-in ended while on the page

  const load = () =>
    fetchBody()
      .then((found) =>
        setLoaded(found === null ? { status: 'signed-out' } : { status: 'ready', ...found }),
      )
      .catch(() => setLoaded({ status: 'error' }))
  useEffect(() => {
    void load()
  }, [])

  if (loaded.status !== 'ready')
    return <Frame embedded={embedded}>{<Status loaded={loaded} />}</Frame>
  const { kinds, entries, guide, estimates, averages } = loaded
  const kindOf = (name: string) => kinds.find((k) => k.kind === name)
  const rows = latest(kinds, entries)
  const rowOf = new Map(rows.map((l) => [l.kind.kind, l]))
  const scaleFat = entries.filter((e) => e.kind === 'body_fat_scale')

  const save = async () => {
    const parsed = parse(kinds, typed)
    if ('invalid' in parsed) return setNote(`${parsed.invalid} isn't a number.`)
    if (Object.keys(parsed.values).length === 0) return setNote('Fill in at least one.')
    setBusy(true)
    setNote(null)
    setWarnings([])
    setSignedOut(false) // a retry after signing in again
    try {
      const answer = await saveBody({ on: day, values: parsed.values })
      if (typeof answer !== 'string') {
        setTyped({})
        setNote('Saved.')
        setWarnings(answer.warnings)
        await load()
      } else setNote(answer)
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't save. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  const remove = async (entry: Measurement) => {
    setNote(null)
    setSignedOut(false) // a retry after signing in again
    try {
      await deleteMeasurement(entry.on, entry.kind)
      await load()
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't remove it. Check your connection and try again.")
    }
  }

  return (
    <Frame embedded={embedded}>
      {!embedded && <h1 className="text-3xl font-extrabold">Body</h1>}
      <Toast text={note} onClose={() => setNote(null)} />
      {signedOut && <SignedOutNotice />}

      {(rows.length > 0 || estimates.length > 0) && (
        <section aria-labelledby="latest" className={card}>
          <h2 id="latest" className="mb-2 text-lg font-bold">
            Latest
          </h2>
          <ul className="flex flex-col gap-2">
            {kinds.map((kind) => {
              const row = rowOf.get(kind.kind)
              if (kind.kind === 'body_fat_scale')
                return row || estimates.length > 0 ? (
                  <li key={kind.kind} className="flex flex-col gap-1">
                    {row ? <Values row={row} /> : <span className="font-bold">Body fat</span>}
                    <BodyFatChart scale={scaleFat} tape={estimates} />
                  </li>
                ) : null
              if (!row) return null
              // Bodyweight's headline is its 7-day average: day to day it moves with water.
              const average = kind.kind === 'bodyweight' ? averages[0] : undefined
              return (
                <li key={kind.kind} className="flex items-center justify-between gap-3">
                  {average ? (
                    <span className="flex flex-col">
                      <span>
                        <span className="font-bold">{kind.label}</span>: 7-day average{' '}
                        {format(kind, average.value)} · from {average.count}{' '}
                        {average.count === 1 ? 'weigh-in' : 'weigh-ins'}
                      </span>
                      <span className="text-sm text-[var(--slate)]">
                        Last weigh-in {format(kind, row.value)} ({row.on})
                      </span>
                    </span>
                  ) : (
                    <Values row={row} />
                  )}
                  <Sparkline
                    values={average ? averages.map((a) => a.value) : row.values}
                    label={
                      average
                        ? `${kind.label}, 7-day average, ${averages.length} days`
                        : `${kind.label}, ${row.values.length} entries`
                    }
                  />
                </li>
              )
            })}
          </ul>
        </section>
      )}

      <section aria-labelledby="add" className={card + ' flex flex-col gap-3'}>
        <h2 id="add" className="text-lg font-bold">
          Add measurements
        </h2>
        {guide && (
          <details className="rounded-xl border border-[var(--line)] px-3">
            <summary className="cursor-pointer py-2.5 font-bold">Before you measure</summary>
            <ul className="m-0 flex flex-col gap-1 pl-5">
              {guide.checklist.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p className="mt-2 mb-3 text-[var(--slate)]">{guide.cadence}</p>
          </details>
        )}
        <label className="flex items-center justify-between gap-3 font-bold">
          Day
          <input
            type="date"
            className="min-h-11 rounded-xl border-2 border-[var(--ink)] px-2"
            value={day}
            min={bounds.min}
            max={bounds.max}
            onChange={(e) => setDay(e.target.value)}
          />
        </label>
        {kinds.map((kind) => (
          <div key={kind.kind} className="flex flex-col">
            <label className="flex items-center justify-between gap-3">
              <span>
                {kind.label} <span className="text-[var(--slate)]">({kind.unit})</span>
              </span>
              <input
                inputMode="decimal"
                aria-label={kind.label}
                className="min-h-11 w-28 rounded-xl border-2 border-[var(--ink)] px-2 text-right text-lg font-bold"
                value={typed[kind.kind] ?? ''}
                onChange={(e) => setTyped({ ...typed, [kind.kind]: e.target.value })}
              />
            </label>
            <details className="text-sm">
              <summary className="w-fit cursor-pointer py-2 text-[var(--slate)]">
                How?<span className="sr-only"> ({kind.label})</span>
              </summary>
              <p className="m-0 mb-1">{kind.how}</p>
            </details>
          </div>
        ))}
        <p className="text-[var(--slate)]">
          Fill in any of them. The same one again that day replaces it.
        </p>
        <button type="button" className={primary} disabled={busy} onClick={save}>
          Save
        </button>
        {warnings.length > 0 && (
          <div
            role="region"
            aria-labelledby="second-look"
            className="flex flex-col gap-2 rounded-xl border-2 border-[var(--bell-ink)] p-3"
          >
            <p id="second-look" className="m-0 font-bold">
              Saved, but worth a second look
            </p>
            <ul className="m-0 flex flex-col gap-1 pl-5">
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
            <button type="button" className={small + ' self-start'} onClick={() => setWarnings([])}>
              Dismiss
            </button>
          </div>
        )}
      </section>

      <Photos />

      {entries.length > 0 && (
        <section aria-labelledby="history" className="flex flex-col gap-3">
          <h2 id="history" className="text-lg font-bold">
            History
          </h2>
          {byDay(entries).map(([on, list]) => (
            <div key={on} className={card}>
              <p className="font-bold">{on}</p>
              <ul className="flex flex-col gap-1">
                {list.map((entry) => {
                  const kind = kindOf(entry.kind)
                  return (
                    <li key={entry.kind} className="flex items-center justify-between gap-3">
                      <span>
                        {kind?.label ?? entry.kind}:{' '}
                        {kind ? format(kind, entry.value) : entry.value}
                      </span>
                      <button
                        type="button"
                        className={small}
                        aria-label={`Remove ${kind?.label ?? entry.kind} on ${on}`}
                        onClick={() => remove(entry)}
                      >
                        Remove
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </section>
      )}
    </Frame>
  )
}

/** A kind's latest value against its first and the one before. */
function Values({ row }: { row: Latest }) {
  return (
    <span>
      <span className="font-bold">{row.kind.label}</span>: {format(row.kind, row.value)}
      {row.first !== null && ` · since first ${change(row.kind, row.value, row.first)}`}
      {row.previous !== null && ` · since last ${change(row.kind, row.value, row.previous)}`}
      <span className="text-[var(--slate)]"> ({row.on})</span>
    </span>
  )
}

function Status({ loaded }: { loaded: Exclude<Loaded, { status: 'ready' }> }) {
  if (loaded.status === 'loading')
    return (
      <p className="status" role="status">
        Loading…
      </p>
    )
  if (loaded.status === 'signed-out') return <SignInCard text="Sign in to see your measurements." />
  return <RetryCard text="Couldn't load your measurements. Check your connection." />
}
