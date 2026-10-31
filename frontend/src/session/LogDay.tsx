import { useRef, useState } from 'react'
import {
  fetchLogOptions,
  fetchLogPlan,
  logDay,
  SignedOutError,
  type Answer,
  type CardioActivity,
  type CardioKind,
  type Clash,
  type LogDay as LogBody,
  type LogOptions,
  type LogPlan,
} from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import ClashQuestion from './ClashQuestion'
import { dayText, recentDays, stepOf, unitText } from './logic'
import { actions, card, primary, secondary } from '../ui'
import { effortLabel } from './safety'

type Kind = CardioKind
type What =
  { kind: 'session'; templateId: number; name: string } | { kind: 'rest' } | { kind: 'cardio' }

const KINDS: { kind: Kind; label: string }[] = [
  { kind: 'zone2', label: 'Easy (zone 2)' },
  { kind: 'moderate-cardio', label: 'Harder (moderate)' },
  { kind: 'hiit', label: 'HIIT' },
]

const chip = (on: boolean) =>
  'min-h-11 rounded-full border-2 px-4 font-bold ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

const setKey = (item: number, setNo: number) => `${item}:${setNo}`

/**
 * "Log another day" (ADR-0060): a day from today back to two weeks, then any session in the
 * plan (with that day's targets), cardio, or a rest day on an earlier day. When that day
 * already has its session, the question comes first and nothing is saved until it's answered.
 * ``onSaved`` gets the text to show; the page then offers Undo.
 */
export default function LogDay({
  onSaved,
  talkTest = false,
}: {
  onSaved: (text: string) => void
  talkTest?: boolean // effort by the talk test, not heart-rate zones (ADR-0083)
}) {
  const [options, setOptions] = useState<LogOptions | null>(null)
  const [open, setOpen] = useState(false)
  const [day, setDay] = useState<string | null>(null)
  const [what, setWhat] = useState<What | null>(null)
  const [plan, setPlan] = useState<LogPlan | null>(null)
  const [values, setValues] = useState<Record<string, number>>({})
  const [extra, setExtra] = useState(false)
  const [kind, setKind] = useState<Kind>('zone2')
  const [activity, setActivity] = useState<CardioActivity | null>(null)
  const [amount, setAmount] = useState(30)
  const [clash, setClash] = useState<Clash | null>(null)
  const [taken, setTaken] = useState<Clash | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [signedOut, setSignedOut] = useState(false)
  // The token and the log it was first sent with: only that same log, sent again (a retry or
  // with an answer), reuses it, so it saves once.
  const sent = useRef<{ token: string; log: string } | null>(null)

  const days = recentDays() // today back two weeks; the server checks the day again
  const today = days[0]
  const label = (d: string) => (d === today ? 'today' : d === days[1] ? 'yesterday' : dayText(d))

  const close = () => {
    setOpen(false)
    setDay(null)
    setWhat(null)
    setPlan(null)
    setClash(null)
    setTaken(null)
    setNote(null)
  }

  const start = async () => {
    setOpen(true)
    setNote(null)
    if (options) return
    try {
      const found = await fetchLogOptions()
      if (found === null) setSignedOut(true)
      else setOptions(found)
    } catch {
      setNote("Couldn't load your plan. Check your connection and try again.")
    }
  }

  const pickSession = async (templateId: number, name: string) => {
    if (!day) return
    setNote(null)
    try {
      const found = await fetchLogPlan(day, templateId)
      const start: Record<string, number> = {}
      found.items.forEach((item, i) =>
        item.targets.forEach((t, n) => (start[setKey(i, n + 1)] = t)),
      )
      setPlan(found)
      setValues(start)
      setExtra(false)
      setWhat({ kind: 'session', templateId, name })
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't load that session. Try again.")
    }
  }

  const body = (): LogBody | null => {
    if (!day || !what) return null
    const base = { token: '', day }
    if (what.kind === 'rest') return { ...base, what: 'rest' }
    if (what.kind === 'cardio')
      return { ...base, what: 'cardio', cardio: kind, value: amount, activity }
    const sets = Object.entries(values)
      .filter(([, v]) => v > 0)
      .map(([k, v]) => {
        const [item, setNo] = k.split(':').map(Number)
        return { item, set_no: setNo, left: v }
      })
    return {
      ...base,
      what: extra ? 'extra' : 'session',
      template_id: what.templateId,
      sets,
    }
  }

  const done = (saved: string, next: string | null) => {
    const text = `Saved ${saved} for ${label(day ?? '')}.${next ? ` Next up: ${next}.` : ''}`
    close()
    onSaved(text)
  }

  const save = async (answer?: Answer) => {
    const found = body()
    if (!found || busy) return
    if (found.what !== 'rest' && found.what !== 'cardio' && found.sets?.length === 0) {
      setNote('Enter at least one set: a set left at 0 counts as not done.')
      return
    }
    const log = JSON.stringify(found)
    if (sent.current?.log !== log)
      sent.current = { token: crypto.randomUUID().replaceAll('-', ''), log }
    setBusy(true)
    setNote(null)
    setSignedOut(false)
    try {
      const result = await logDay({ ...found, token: sent.current.token, ...answer })
      if (result === 'stale') {
        setNote('The plan changed meanwhile. Start again.')
      } else if ('problem' in result) {
        setNote(result.problem)
      } else if ('clash' in result) {
        if (result.clash.moving) setTaken(result.clash)
        else {
          if (clash) setNote('That day changed since you looked. Here it is now.')
          setClash(result.clash)
          setTaken(null)
        }
      } else {
        sent.current = null
        const saved =
          what?.kind === 'session'
            ? extra
              ? `an extra (${what.name})`
              : what.name
            : what?.kind === 'rest'
              ? 'a rest day'
              : 'cardio'
        done(saved, result.next_session)
      }
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

  if (!open)
    return (
      <section aria-labelledby="log-day" className={`${card} flex flex-col gap-3`}>
        <h2 id="log-day" className="m-0 text-lg font-bold">
          Log another day
        </h2>
        <p className="m-0 text-[var(--slate)]">
          A day you didn't log, or a different session today.
        </p>
        <div className={actions}>
          <button type="button" className={secondary} onClick={start}>
            Log another day
          </button>
        </div>
      </section>
    )

  if (clash)
    return (
      <div className="flex flex-col gap-3">
        {feedback}
        <ClashQuestion
          clash={clash}
          taken={taken}
          busy={busy}
          onAnswer={save}
          onCancel={() => {
            setClash(null)
            setTaken(null)
          }}
        />
      </div>
    )

  const back = (onClick: () => void) => (
    <button type="button" className={secondary} onClick={onClick}>
      Back
    </button>
  )

  return (
    <section aria-labelledby="log-day" className={`${card} flex flex-col gap-4`}>
      {feedback}
      {!day && (
        <>
          <h2 id="log-day" className="m-0 text-2xl font-extrabold">
            Which day?
          </h2>
          {options && (
            <div className={actions}>
              {days.map((d) => (
                <button key={d} type="button" className={chip(false)} onClick={() => setDay(d)}>
                  {d === today ? 'Today' : d === days[1] ? 'Yesterday' : dayText(d)}
                </button>
              ))}
            </div>
          )}
          <button type="button" className={secondary} onClick={close}>
            Cancel
          </button>
        </>
      )}

      {day && !what && options && (
        <>
          <h2 id="log-day" className="m-0 text-2xl font-extrabold">
            What did you do {label(day)}?
          </h2>
          <div className="flex flex-col gap-2">
            {options.sessions.map((s) => (
              <button
                key={s.template_id}
                type="button"
                className={secondary}
                onClick={() => pickSession(s.template_id, s.name)}
              >
                {s.name}
              </button>
            ))}
            <button type="button" className={secondary} onClick={() => setWhat({ kind: 'cardio' })}>
              Cardio or HIIT
            </button>
            {day !== today && (
              <button type="button" className={secondary} onClick={() => setWhat({ kind: 'rest' })}>
                Rest day
              </button>
            )}
          </div>
          {back(() => setDay(null))}
        </>
      )}

      {day && what?.kind === 'rest' && (
        <>
          <h2 id="log-day" className="m-0 text-2xl font-extrabold">
            A rest day {label(day)}
          </h2>
          <p className="m-0 text-[var(--slate)]">No sets, and the plan stays where it is.</p>
          <button type="button" className={primary} disabled={busy} onClick={() => save()}>
            Save the rest day
          </button>
          {back(() => setWhat(null))}
        </>
      )}

      {day && what?.kind === 'cardio' && (
        <>
          <h2 id="log-day" className="m-0 text-2xl font-extrabold">
            Cardio {label(day)}
          </h2>
          <div className="grid grid-cols-3 gap-2">
            {KINDS.map((k) => (
              <button
                key={k.kind}
                type="button"
                aria-pressed={kind === k.kind}
                className={chip(kind === k.kind)}
                onClick={() => {
                  setKind(k.kind)
                  setAmount(k.kind === 'hiit' ? 8 : 30)
                }}
              >
                {effortLabel(k.kind, talkTest, k.label)}
              </button>
            ))}
          </div>
          <fieldset className="flex flex-col gap-2 border-0 p-0">
            <legend className="mb-2 font-bold">What it was</legend>
            <div className={actions}>
              {(options?.activities ?? []).map((a) => (
                <button
                  key={a}
                  type="button"
                  aria-pressed={activity === a}
                  className={chip(activity === a)}
                  onClick={() => setActivity(activity === a ? null : a)}
                >
                  {a[0].toUpperCase() + a.slice(1)}
                </button>
              ))}
            </div>
          </fieldset>
          <Stepper
            label={kind === 'hiit' ? 'Rounds' : 'Minutes'}
            value={amount}
            step={kind === 'hiit' ? 1 : 5}
            min={1}
            onChange={setAmount}
          />
          <button type="button" className={primary} disabled={busy} onClick={() => save()}>
            Save {amount} {kind === 'hiit' ? 'rounds' : 'min'}
          </button>
          {back(() => setWhat(null))}
        </>
      )}

      {day && what?.kind === 'session' && plan && (
        <>
          <h2 id="log-day" className="m-0 text-2xl font-extrabold">
            {plan.name} {label(day)}
          </h2>
          <p className="m-0 text-[var(--slate)]">
            Set to the targets: change what was different. A set at 0 wasn't done.
          </p>
          {plan.items.map((item, i) => (
            <fieldset key={item.slug} className="flex flex-col gap-2 border-0 p-0">
              <legend className="font-bold">
                {item.name}
                {item.per_side ? ' (each side)' : ''}
              </legend>
              {item.targets.map((t, n) => (
                <Stepper
                  key={n}
                  label={`${item.name} set ${n + 1}`}
                  shown={`Set ${n + 1}`}
                  value={values[setKey(i, n + 1)] ?? t}
                  step={stepOf(item)}
                  min={0}
                  unit={unitText(item, values[setKey(i, n + 1)] ?? t).replace(/^\d+\s?/, '')}
                  onChange={(v) => setValues({ ...values, [setKey(i, n + 1)]: v })}
                />
              ))}
            </fieldset>
          ))}
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={extra} onChange={(e) => setExtra(e.target.checked)} />
            An extra: it doesn't count as {plan.name}
          </label>
          <button type="button" className={primary} disabled={busy} onClick={() => save()}>
            Save {extra ? 'the extra' : plan.name}
          </button>
          {back(() => setWhat(null))}
        </>
      )}
    </section>
  )
}

/** A number nudged with − and + or typed, never below ``min``. */
function Stepper({
  label,
  shown,
  value,
  step,
  min,
  unit,
  onChange,
}: {
  label: string
  shown?: string
  value: number
  step: number
  min: number
  unit?: string
  onChange: (value: number) => void
}) {
  const set = (v: number) => onChange(Math.min(3600, Math.max(min, Math.round(v))))
  return (
    <div className="flex items-center gap-2" role="group" aria-label={label}>
      {shown && <span className="w-14 text-sm text-[var(--slate)]">{shown}</span>}
      {!shown && <span className="w-20 font-bold">{label}</span>}
      <button
        type="button"
        aria-label={`${label}: ${step} fewer`}
        className="size-11 rounded-full border-2 border-[var(--ink)] font-bold"
        onClick={() => set(value - step)}
      >
        −
      </button>
      <input
        type="number"
        inputMode="numeric"
        aria-label={label}
        min={min}
        value={value}
        onChange={(e) => set(Number(e.target.value) || 0)}
        className="w-16 text-center text-xl font-extrabold"
      />
      <button
        type="button"
        aria-label={`${label}: ${step} more`}
        className="size-11 rounded-full border-2 border-[var(--ink)] font-bold"
        onClick={() => set(value + step)}
      >
        +
      </button>
      {unit && <span className="text-sm text-[var(--slate)]">{unit}</span>}
    </div>
  )
}
