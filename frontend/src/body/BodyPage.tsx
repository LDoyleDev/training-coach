import { useEffect, useState } from 'react'
import { deleteMeasurement, fetchBody, saveBody, type MeasureKind, type Measurement } from '../api'
import { byDay, change, format, isoDay, latest, parse } from './logic'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; kinds: MeasureKind[]; entries: Measurement[] }

const card = 'rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4'
const primary =
  'min-h-14 w-full rounded-2xl bg-[var(--bell-ink)] px-4 text-lg font-bold text-white disabled:opacity-60'
const small = 'min-h-11 rounded-xl border-2 border-[var(--ink)] px-3 font-bold text-[var(--ink)]'

/** /body: measurements (2-B, #142). Personal: never in a share view. */
export default function BodyPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [typed, setTyped] = useState<Record<string, string>>({})
  const [day, setDay] = useState(() => isoDay(new Date()))
  const [bounds] = useState(() => ({ min: isoDay(new Date(), 14), max: isoDay(new Date()) }))
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () =>
    fetchBody()
      .then((found) =>
        setLoaded(found === null ? { status: 'signed-out' } : { status: 'ready', ...found }),
      )
      .catch(() => setLoaded({ status: 'error' }))
  useEffect(() => {
    void load()
  }, [])

  if (loaded.status !== 'ready') return <Shell>{<Status loaded={loaded} />}</Shell>
  const { kinds, entries } = loaded
  const kindOf = (name: string) => kinds.find((k) => k.kind === name)

  const save = async () => {
    const parsed = parse(kinds, typed)
    if ('invalid' in parsed) return setNote(`${parsed.invalid} isn't a number.`)
    if (Object.keys(parsed.values).length === 0) return setNote('Fill in at least one.')
    setBusy(true)
    setNote(null)
    try {
      const answer = await saveBody({ on: day, values: parsed.values })
      if (answer === true) {
        setTyped({})
        setNote('Saved.')
        await load()
      } else setNote(answer)
    } catch {
      setNote("Couldn't save. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  const remove = async (entry: Measurement) => {
    try {
      await deleteMeasurement(entry.on, entry.kind)
      await load()
    } catch {
      setNote("Couldn't remove it. Check your connection and try again.")
    }
  }

  return (
    <Shell>
      <h1 className="text-3xl font-extrabold">Body</h1>
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}

      {latest(kinds, entries).length > 0 && (
        <section aria-labelledby="latest" className={card}>
          <h2 id="latest" className="mb-2 text-lg font-bold">
            Latest
          </h2>
          <ul className="flex flex-col gap-1">
            {latest(kinds, entries).map((l) => (
              <li key={l.kind.kind}>
                <span className="font-bold">{l.kind.label}</span>: {format(l.kind, l.value)}
                {l.first !== null && ` · since first ${change(l.kind, l.value, l.first)}`}
                {l.previous !== null && ` · since last ${change(l.kind, l.value, l.previous)}`}
                <span className="text-[var(--slate)]"> ({l.on})</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="add" className={card + ' flex flex-col gap-3'}>
        <h2 id="add" className="text-lg font-bold">
          Add measurements
        </h2>
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
          <label key={kind.kind} className="flex items-center justify-between gap-3">
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
        ))}
        <p className="text-[var(--slate)]">
          Fill in any of them. The same one again that day replaces it.
        </p>
        <button type="button" className={primary} disabled={busy} onClick={save}>
          Save
        </button>
      </section>

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
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="page">
      <header className="masthead">
        <span className="wordmark">Training Coach</span>
      </header>
      <main className="flex flex-col gap-4">{children}</main>
    </div>
  )
}

function Status({ loaded }: { loaded: Exclude<Loaded, { status: 'ready' }> }) {
  if (loaded.status === 'loading')
    return (
      <p className="status" role="status">
        Loading…
      </p>
    )
  if (loaded.status === 'signed-out')
    return (
      <p className="status">
        Sign in to see your measurements. <a href="/signin">Sign in</a>
      </p>
    )
  return (
    <p className="status status-error" role="alert">
      Couldn't load your measurements. Check your connection and reload the page.
    </p>
  )
}
