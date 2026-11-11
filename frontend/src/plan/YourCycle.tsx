import { useState } from 'react'
import { card, danger, primaryInline, small } from '../ui'
import { cannotAdd, days, MAX_DAYS, MAX_REST, problem, suggestedAfter } from './cycleLogic'
import {
  added,
  EMPTY_CARDIO,
  freeName,
  KINDS,
  kinded,
  kindLabel,
  lengthLine,
  moved,
  NEW,
  newKey,
  removed,
  removeQuestion,
  renamed,
  rested,
  thenRest,
  weekLine,
  type Entry,
  type Kind,
} from './cycleDraft'

const NAME_MAX = 40 // Decided 3: the server says so in words past it

function AddForm({
  cycle,
  onAdd,
  onClose,
}: {
  cycle: Entry[]
  onAdd: (cycle: Entry[], entry: Entry) => void
  onClose: () => void
}) {
  const saved = cycle.filter((e) => typeof e.key === 'number')
  const [from, setFrom] = useState('') // '': empty, else the copied session's slug
  const [name, setName] = useState(() => freeName('New session', cycle, true))
  const [kind, setKind] = useState<Kind>('strength')
  const [after, setAfter] = useState(() => String(suggestedAfter(cycle)))
  const key = newKey(cycle)
  const entry: Entry = {
    key,
    restAfter: 0,
    slug: NEW + key,
    name,
    kind,
    copyOf: from || null,
    logged: 0,
  }
  const goesAfter = cycle.find((e) => String(e.key) === after)!.key
  const next = added(cycle, entry, goesAfter)
  const refused = problem(next)
  return (
    <form
      className="flex flex-col gap-3 rounded-xl border border-[var(--line)] p-3"
      aria-label="Add a session"
      onSubmit={(e) => {
        e.preventDefault()
        onAdd(next, entry)
      }}
    >
      <label className="flex flex-col gap-1">
        <span>Start from</span>
        <select
          className="min-h-11"
          value={from}
          onChange={(e) => {
            const copy = saved.find((s) => s.slug === e.target.value)
            setFrom(e.target.value)
            setName(copy ? freeName(copy.name, cycle, false) : freeName('New session', cycle, true))
            setKind(copy?.kind ?? 'strength')
          }}
        >
          <option value="">Empty</option>
          {saved.map((s) => (
            <option key={s.slug} value={s.slug}>
              A copy of {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span>Name</span>
        <input
          type="text"
          className="min-h-11"
          maxLength={NAME_MAX}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-1">Kind</legend>
        {KINDS.map((k) => (
          <label key={k.kind} className="flex items-start gap-2">
            <input
              type="radio"
              name="kind"
              className="mt-1 shrink-0"
              checked={kind === k.kind}
              aria-labelledby={`kind-name-${k.kind}`}
              aria-describedby={`kind-${k.kind}`}
              onChange={() => setKind(k.kind)}
            />
            <span className="flex flex-col">
              <span id={`kind-name-${k.kind}`} className="font-bold">
                {k.label}
              </span>
              <span id={`kind-${k.kind}`} className="text-sm">
                {k.line}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      {!from && kind === 'conditioning' && (
        <p className="m-0 text-[var(--bell-ink)]">{EMPTY_CARDIO}</p>
      )}
      <label className="flex flex-col gap-1">
        <span>Goes after</span>
        <select className="min-h-11" value={after} onChange={(e) => setAfter(e.target.value)}>
          {cycle.map((e) => (
            <option key={e.slug} value={String(e.key)}>
              {e.name}
            </option>
          ))}
        </select>
      </label>
      <p className="m-0">{weekLine(next, 'With it, your cycle')}</p>
      {refused && <p className="m-0 text-[var(--bell-ink)]">{refused}</p>}
      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          className={primaryInline}
          disabled={refused !== null || name.trim() === ''}
        >
          Add
        </button>
        <button type="button" className={small} onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  )
}

function Rename({
  entry,
  onDone,
  onClose,
}: {
  entry: Entry
  onDone: (name: string) => void
  onClose: () => void
}) {
  const [name, setName] = useState(entry.name)
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        onDone(name.trim())
      }}
    >
      <label className="flex flex-col gap-1">
        <span>New name for {entry.name}</span>
        <input
          type="text"
          className="min-h-11"
          maxLength={NAME_MAX}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <button type="submit" className={small} disabled={name.trim() === ''}>
        Done
      </button>
      <button type="button" className={small} onClick={onClose}>
        Cancel
      </button>
    </form>
  )
}

/** The Your cycle card on /plan/edit (ADR-0093): the sessions in queue order with their rest
 * days, the week they make, Add a session, and per session Rename, its kind, Up and Down, Remove
 * and its rest days. Every change is a draft until Save. */
export default function YourCycle({
  cycle,
  next,
  onChange,
  onAdd,
}: {
  cycle: Entry[]
  next: string | null // the slug the queue offers next
  onChange: (cycle: Entry[]) => void
  onAdd: (cycle: Entry[], entry: Entry) => void
}) {
  const [adding, setAdding] = useState(false)
  const [renaming, setRenaming] = useState<Entry['key'] | null>(null)
  const [removing, setRemoving] = useState<Entry['key'] | null>(null)
  const full = cannotAdd(cycle)
  const length = days(cycle)
  const often = lengthLine(length)
  return (
    <section className={`${card} flex flex-col gap-3`} aria-labelledby="your-cycle">
      <h2 id="your-cycle" className="m-0 text-xl font-bold">
        Your cycle
      </h2>
      <ol className="m-0 flex list-none flex-col gap-2 p-0">
        {cycle.map((e, at) => (
          <li
            key={e.slug}
            className="flex flex-col gap-2 rounded-xl border border-[var(--line)] p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-bold">{e.name}</span>
              {e.slug === next && (
                <span className="rounded-full bg-[var(--bell-ink)] px-2 text-sm font-bold text-[var(--chalk)]">
                  Next
                </span>
              )}
            </div>
            <span className="text-[var(--slate)]">
              {kindLabel(e.kind)} · {thenRest(e.restAfter)}
            </span>
            {renaming === e.key ? (
              <Rename
                entry={e}
                onClose={() => setRenaming(null)}
                onDone={(name) => {
                  onChange(renamed(cycle, e.key, name))
                  setRenaming(null)
                }}
              />
            ) : removing === e.key ? (
              <div className="flex flex-col gap-2" role="group" aria-label={`Remove ${e.name}`}>
                <p className="m-0">{removeQuestion(e)}</p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={danger}
                    onClick={() => {
                      onChange(removed(cycle, e.key))
                      setRemoving(null)
                    }}
                  >
                    Remove
                  </button>
                  <button type="button" className={small} onClick={() => setRemoving(null)}>
                    Keep it
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className={small}
                  aria-label={`Rename ${e.name}`}
                  onClick={() => setRenaming(e.key)}
                >
                  Rename
                </button>
                <button
                  type="button"
                  className={small}
                  aria-label={`Move ${e.name} up`}
                  disabled={at === 0}
                  onClick={() => onChange(moved(cycle, e.key, -1))}
                >
                  Up
                </button>
                <button
                  type="button"
                  className={small}
                  aria-label={`Move ${e.name} down`}
                  disabled={at === cycle.length - 1}
                  onClick={() => onChange(moved(cycle, e.key, 1))}
                >
                  Down
                </button>
                <label className="flex items-center gap-2">
                  <span>Kind</span>
                  <select
                    className="min-h-11"
                    aria-label={`Kind of ${e.name}`}
                    value={e.kind}
                    onChange={(ev) => onChange(kinded(cycle, e.key, ev.target.value as Kind))}
                  >
                    {KINDS.map((k) => (
                      <option key={k.kind} value={k.kind}>
                        {k.label}
                      </option>
                    ))}
                  </select>
                </label>
                {cycle.length > 1 && ( // the last session can't be removed (Decided 5)
                  <button
                    type="button"
                    className={small}
                    aria-label={`Remove ${e.name}`}
                    onClick={() => setRemoving(e.key)}
                  >
                    Remove
                  </button>
                )}
                <div
                  className="flex items-center gap-2"
                  role="group"
                  aria-label={`Rest days after ${e.name}`}
                >
                  <span>Rest days after</span>
                  <button
                    type="button"
                    className={small}
                    aria-label={`One rest day fewer after ${e.name}`}
                    disabled={e.restAfter <= 0}
                    onClick={() => onChange(rested(cycle, e.key, e.restAfter - 1))}
                  >
                    −
                  </button>
                  <span className="tabular-nums">{e.restAfter}</span>
                  <button
                    type="button"
                    className={small}
                    aria-label={`One rest day more after ${e.name}`}
                    disabled={e.restAfter >= MAX_REST || length >= MAX_DAYS}
                    onClick={() => onChange(rested(cycle, e.key, e.restAfter + 1))}
                  >
                    +
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ol>
      <p className="m-0">{weekLine(cycle)}</p>
      {often && <p className="m-0 text-[var(--slate)]">{often}</p>}
      {adding ? (
        <AddForm
          cycle={cycle}
          onClose={() => setAdding(false)}
          onAdd={(now, entry) => {
            setAdding(false)
            onAdd(now, entry)
          }}
        />
      ) : (
        <div className="flex flex-col gap-1">
          <button
            type="button"
            className={`${small} self-start`}
            disabled={full !== null}
            aria-describedby={full ? 'cannot-add' : undefined}
            onClick={() => setAdding(true)}
          >
            Add a session
          </button>
          {full && (
            <p id="cannot-add" className="m-0 text-[var(--slate)]">
              {full}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
