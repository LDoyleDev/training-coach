import { useCallback, useEffect, useState } from 'react'
import { fetchToday, keepProgress, saveSession, type Guided, type Saved } from '../api'
import {
  fromKept,
  key,
  partnerOf,
  stepOf,
  summary,
  toDone,
  unitText,
  valueFor,
  versus,
  type Value,
  type Values,
} from './logic'

type Stage = 'overview' | 'set' | 'check' | 'saved'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'none' } // nothing planned left today
  | { status: 'ready'; session: Guided }

const card = 'rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4'
const primary =
  'min-h-14 w-full rounded-2xl bg-[var(--bell-ink)] px-4 text-lg font-bold text-white disabled:opacity-60'
const secondary =
  'min-h-11 rounded-xl border-2 border-[var(--ink)] px-4 font-bold text-[var(--ink)]'

/**
 * /session: today's session one set at a time (D1, docs/specs/dashboard-design.md). Every
 * confirmed set is kept on the server (#117), so Leave keeps the place on any device; nothing
 * becomes a workout until Save session.
 */
export default function SessionPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [stage, setStage] = useState<Stage>('overview')
  const [position, setPosition] = useState(0)
  const [values, setValues] = useState<Values>({})
  const [revision, setRevision] = useState(0)
  const [note, setNote] = useState<string | null>(null)
  const [saved, setSaved] = useState<Saved | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    fetchToday()
      .then((today) => {
        if (today === null) return setLoaded({ status: 'signed-out' })
        if (today.session === null) return setLoaded({ status: 'none' })
        setLoaded({ status: 'ready', session: today.session })
        setValues(fromKept(today.progress))
        setPosition(today.progress?.position ?? 0)
        setRevision(today.progress?.revision ?? 0)
      })
      .catch(() => setLoaded({ status: 'error' }))
  }, [])

  useEffect(load, [load])

  if (loaded.status !== 'ready') return <Shell>{<Status loaded={loaded} />}</Shell>
  const session = loaded.session
  const total = session.order.length

  /** Keep the place and the sets; another device having moved on reloads its version. */
  const keep = async (nextPosition: number, nextValues: Values): Promise<boolean> => {
    setBusy(true)
    try {
      const result = await keepProgress({
        template_id: session.template_id,
        revision,
        position: nextPosition,
        first: [],
        sets: toDone(session, nextValues),
      })
      if (result === 'stale') {
        setNote('This session moved on from another device; here is where it is now.')
        load()
        return false
      }
      setRevision(result)
      return true
    } catch {
      setNote("Couldn't save that set. Check your connection and confirm again.")
      return false
    } finally {
      setBusy(false)
    }
  }

  const step = session.order[Math.min(position, total - 1)]
  const item = session.items[step.item]
  const value = valueFor(values, step.item, step.set_no, step.target)
  const change = (v: Value) => setValues({ ...values, [key(step.item, step.set_no)]: v })

  const confirm = async () => {
    const nextValues = { ...values, [key(step.item, step.set_no)]: value }
    const next = position + 1
    if (await keep(next, nextValues)) {
      setNote(null)
      setValues(nextValues)
      setPosition(next)
      if (next >= total) setStage('check')
    }
  }

  const save = async () => {
    setBusy(true)
    try {
      const result = await saveSession()
      if (result === 'stale') {
        setNote("Today's session changed (a rest, swap or another log), so this wasn't saved.")
        return
      }
      setSaved(result)
      setStage('saved')
    } catch {
      setNote("Couldn't save. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell>
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}

      {stage === 'overview' && (
        <Overview
          session={session}
          resumeAt={position > 0 && position < total ? position : null}
          onStart={() => setStage(position >= total ? 'check' : 'set')}
        />
      )}

      {stage === 'set' && (
        <section aria-labelledby="exercise" className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <button type="button" className={secondary} onClick={() => setStage('overview')}>
              Leave
            </button>
            <span className="text-sm text-[var(--slate)]">
              Set {position + 1} of {total}
            </span>
            <button
              type="button"
              className={secondary}
              disabled={position === 0}
              onClick={() => setPosition(position - 1)}
            >
              Back
            </button>
          </div>
          <progress
            max={total}
            value={position + 1}
            aria-label="Session progress"
            className="w-full"
          />
          <div>
            <p className="text-sm font-bold tracking-wide text-[var(--bell-ink)]">
              {partnerOf(session, step.item)
                ? `PAIR ${item.pair} · ALTERNATE WITH ${partnerOf(session, step.item)?.name.toUpperCase()}`
                : 'ON ITS OWN'}
            </p>
            <h1 id="exercise" className="text-4xl font-extrabold">
              {item.name}
            </h1>
            <p className="text-[var(--slate)]">{item.step}</p>
          </div>
          {item.summary && <p className={card}>{item.summary}</p>}
          <div className="flex items-baseline justify-between">
            <span className="text-lg font-bold">
              Set {step.set_no} of {item.targets.length}
            </span>
            <span className="text-[var(--slate)]">
              Target {unitText(item, step.target)}
              {item.per_side ? ' each side' : ''}
            </span>
          </div>
          {item.per_side && value.split ? (
            <>
              <Counter
                label="Left"
                value={value.left}
                step={stepOf(item)}
                target={step.target}
                onChange={(left) => change({ ...value, left })}
              />
              <Counter
                label="Right"
                value={value.right}
                step={stepOf(item)}
                target={step.target}
                onChange={(right) => change({ ...value, right })}
              />
            </>
          ) : (
            <Counter
              label={item.per_side ? 'Each side' : item.unit === 'reps' ? 'Reps' : item.unit}
              value={value.left}
              step={stepOf(item)}
              target={step.target}
              onChange={(v) => change({ ...value, left: v, right: v })}
            />
          )}
          {item.per_side && (
            <button
              type="button"
              aria-pressed={value.split}
              className="min-h-11 font-bold text-[var(--bell-ink)] underline"
              onClick={() => change({ ...value, split: !value.split, right: value.left })}
            >
              {value.split ? 'Same on both sides' : 'Left and right differ'}
            </button>
          )}
          <button type="button" className={primary} disabled={busy} onClick={confirm}>
            Confirm set
          </button>
        </section>
      )}

      {stage === 'check' && (
        <section aria-labelledby="check" className="flex flex-col gap-4">
          <h1 id="check" className="text-4xl font-extrabold">
            Check and save
          </h1>
          <p className="text-[var(--slate)]">Nothing is saved until you save.</p>
          <ul className={card}>
            {summary(session, values).map((row) => (
              <li
                key={row.name}
                className="flex justify-between gap-3 border-b border-[var(--line)] py-2"
              >
                <span>
                  <span className="font-bold">{row.name}</span>
                  <br />
                  <span className="text-sm text-[var(--slate)]">target {row.target}</span>
                </span>
                <span className="font-bold">{row.done}</span>
              </li>
            ))}
          </ul>
          <div className="flex gap-3">
            <button
              type="button"
              className={secondary}
              onClick={() => {
                setPosition(total - 1)
                setStage('set')
              }}
            >
              Back
            </button>
            <button type="button" className={primary} disabled={busy} onClick={save}>
              Save session
            </button>
          </div>
        </section>
      )}

      {stage === 'saved' && saved && (
        <section aria-labelledby="saved" className="flex flex-col gap-4">
          <p className="font-bold text-[var(--ink)]">Saved</p>
          <h1 id="saved" className="text-4xl font-extrabold">
            {session.name} done
          </h1>
          {saved.next_session && <p>Next up: {saved.next_session}.</p>}
          {saved.earned.length > 0 && (
            <ul className={card}>
              {saved.earned.map((e) => (
                <li key={e.exercise}>
                  {e.exercise}
                  {e.best_set !== null ? `: new best ${e.best_set} in one set` : ''}
                  {e.next_step ? ` · ready to move up to ${e.next_step}` : ''}
                </li>
              ))}
            </ul>
          )}
          <a href="/" className={secondary + ' flex items-center justify-center'}>
            Done
          </a>
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
        Loading today's session…
      </p>
    )
  if (loaded.status === 'signed-out')
    return (
      <p className="status">
        Sign in to start today's session. <a href="/signin">Sign in</a>
      </p>
    )
  if (loaded.status === 'none')
    return <p className="status">Nothing left to train today. Enjoy the rest.</p>
  return (
    <p className="status status-error" role="alert">
      Couldn't load today's session. Check your connection and reload the page.
    </p>
  )
}

function Overview({
  session,
  resumeAt,
  onStart,
}: {
  session: Guided
  resumeAt: number | null
  onStart: () => void
}) {
  return (
    <section aria-labelledby="session" className="flex flex-col gap-4">
      <p className="text-sm text-[var(--slate)]">About {session.minutes} min</p>
      <h1 id="session" className="text-5xl font-extrabold">
        {session.name}
      </h1>
      <p className="text-[var(--slate)]">{session.focus}</p>
      {session.warm_up && <p className={card}>Warm up for about 10 minutes first.</p>}
      <ul className="flex flex-col gap-2">
        {session.items.map((item) => (
          <li key={item.slug} className={card + ' flex justify-between gap-3'}>
            <span>
              <span className="font-bold">{item.name}</span>
              <br />
              <span className="text-sm text-[var(--slate)]">
                {item.pair !== null ? `Pair ${item.pair} · ` : ''}
                {item.step}
              </span>
            </span>
            <span className="font-bold whitespace-nowrap">
              {item.targets.length} × {unitText(item, item.targets[0])}
              {item.per_side ? ' each side' : ''}
            </span>
          </li>
        ))}
      </ul>
      <button type="button" className={primary} onClick={onStart}>
        {resumeAt !== null
          ? `Resume: set ${resumeAt + 1} of ${session.order.length}`
          : 'Start session'}
      </button>
    </section>
  )
}

function Counter({
  label,
  value,
  step,
  target,
  onChange,
}: {
  label: string
  value: number
  step: number
  target: number
  onChange: (value: number) => void
}) {
  return (
    <div className={card + ' flex flex-col items-center gap-2'} role="group" aria-label={label}>
      <span className="text-sm font-bold text-[var(--slate)]">{label}</span>
      <div className="flex items-center gap-5">
        <button
          type="button"
          aria-label={`${step} fewer`}
          className="size-16 rounded-full border-2 border-[var(--ink)] text-3xl"
          onClick={() => onChange(Math.max(0, value - step))}
        >
          −
        </button>
        <span aria-live="polite" className="min-w-24 text-center text-7xl font-extrabold">
          {value}
        </span>
        <button
          type="button"
          aria-label={`${step} more`}
          className="size-16 rounded-full border-2 border-[var(--ink)] text-3xl"
          onClick={() => onChange(value + step)}
        >
          +
        </button>
      </div>
      <span className="text-sm text-[var(--slate)]">{versus(value, target)}</span>
    </div>
  )
}
