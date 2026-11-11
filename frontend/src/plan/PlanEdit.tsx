import { useEffect, useMemo, useState } from 'react'
import {
  fetchPlanEdit,
  previewCoverage,
  savePlanChanges,
  SignedOutError,
  type CatalogueItem,
  type EditItem,
  type Place,
  type PlanEdit as Loaded,
} from '../api'
import { BodyMap } from '../bodymap/BodyMap'
import type { State as MapState } from '../bodymap/useCoverage'
import AppShell from '../components/AppShell'
import { FigureAt } from '../figures/Figure'
import { RetryCard, SignInCard } from '../components/StateCards'
import { card, primaryInline, secondary, small } from '../ui'
import {
  changed,
  choices,
  draftOf,
  moved,
  muscles,
  pickerLine,
  newItem,
  paired,
  PLACES,
  removed,
  swapped,
  togglePair,
  withItem,
  type Draft,
} from './editLogic'
import {
  baselines,
  cardioWarning,
  cycleBody,
  cycleChanged,
  cycleOf,
  NEW,
  savingWill,
  type Entry,
} from './cycleDraft'
import { days } from './cycleLogic'
import YourCycle from './YourCycle'

type State =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; loaded: Loaded; draft: Draft; cycle: Entry[] }

const WHY: Record<string, string> = {
  stale: 'Your plan changed since you opened this. Reload to see it, then make your edit again.',
  'in-progress': 'Finish or discard your session in progress first: its sets follow today’s list.',
}

const readyOf = (loaded: Loaded): State => ({
  status: 'ready',
  loaded,
  draft: draftOf(loaded.sessions),
  cycle: cycleOf(loaded.sessions),
})

const SETTLE_MS = 400 // after the last tap, ask for the map once

const number = (text: string) => {
  const found = Number(text)
  return Number.isInteger(found) && found >= 1 ? found : null
}

function Picker({
  catalogue,
  place,
  label,
  initial = '',
  onPick,
  onClose,
}: {
  catalogue: CatalogueItem[]
  place: Place
  label: string
  initial?: string // the muscle it opens on: one tapped on the map
  onPick: (from: CatalogueItem) => void
  onClose: () => void
}) {
  const [muscle, setMuscle] = useState(initial)
  const list = choices(catalogue, place, muscle || null)
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-[var(--line)] p-3">
      <label className="flex flex-col gap-1">
        <span>{label}: what should it train?</span>
        <select value={muscle} onChange={(e) => setMuscle(e.target.value)} className="min-h-11">
          <option value="">Anything</option>
          {muscles(catalogue).map((m) => (
            <option key={m} value={m}>
              {m.replaceAll('_', ' ')}
            </option>
          ))}
        </select>
      </label>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {list.map((e) => (
          <li key={e.slug}>
            <button
              type="button"
              aria-labelledby={`pick-${e.slug}`}
              aria-describedby={`line-${e.slug}`}
              className={`${small} flex w-full items-center gap-3 text-left`}
              onClick={() => onPick(e)}
            >
              <span className="w-14 shrink-0" aria-hidden="true">
                <FigureAt slug={e.slug} step={e.first_step} t={0} label="" />
              </span>
              <span className="flex flex-col">
                <span id={`pick-${e.slug}`}>{e.name}</span>
                <span id={`line-${e.slug}`} className="text-sm font-normal">
                  {pickerLine(e)}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className={`${small} self-start`} onClick={onClose}>
        Cancel
      </button>
    </div>
  )
}

function Row({
  item,
  at,
  items,
  set,
  onSwap,
}: {
  item: EditItem
  at: number
  items: EditItem[]
  set: (items: EditItem[]) => void
  onSwap: () => void
}) {
  const range = (key: 'rep_min' | 'rep_max', label: string) => (
    <label className="flex flex-col gap-1">
      <span>{label}</span>
      <input
        type="number"
        min={1}
        value={item[key]}
        className="min-h-11 w-20"
        onChange={(e) => {
          const found = number(e.target.value)
          if (found !== null) set(withItem(items, at, { [key]: found }))
        }}
      />
    </label>
  )
  return (
    <li className="flex flex-col gap-2 rounded-xl border border-[var(--line)] p-3">
      <span className="font-bold">{item.name}</span>
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex items-center gap-2" role="group" aria-label={`Sets of ${item.name}`}>
          <button
            type="button"
            className={small}
            aria-label={`One set fewer of ${item.name}`}
            disabled={item.sets <= 1}
            onClick={() => set(withItem(items, at, { sets: item.sets - 1 }))}
          >
            −
          </button>
          <span className="tabular-nums">{item.sets} sets</span>
          <button
            type="button"
            className={small}
            aria-label={`One set more of ${item.name}`}
            disabled={item.sets >= 20}
            onClick={() => set(withItem(items, at, { sets: item.sets + 1 }))}
          >
            +
          </button>
        </div>
        {range('rep_min', 'From')}
        {range('rep_max', 'To')}
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={small}
          disabled={at === 0}
          aria-label={`Move ${item.name} up`}
          onClick={() => set(moved(items, at, -1))}
        >
          Up
        </button>
        <button
          type="button"
          className={small}
          disabled={at === items.length - 1}
          aria-label={`Move ${item.name} down`}
          onClick={() => set(moved(items, at, 1))}
        >
          Down
        </button>
        <button type="button" className={small} onClick={onSwap} aria-label={`Swap ${item.name}`}>
          Swap
        </button>
        <button
          type="button"
          className={small}
          aria-label={`Remove ${item.name}`}
          onClick={() => set(removed(items, at))}
        >
          Remove
        </button>
        {at < items.length - 1 && (
          <button
            type="button"
            className={small}
            aria-pressed={paired(items, at)}
            aria-label={`Alternate ${item.name} with the next`}
            onClick={() => set(togglePair(items, at))}
          >
            Alternate with next
          </button>
        )}
      </div>
    </li>
  )
}

/** /plan/edit: your own plan, a session and place at a time (builder step 6). Nothing changes until
 * Save, which makes one version with your note. Only what the app couldn't run is refused. */
export default function PlanEdit() {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [slug, setSlug] = useState<string | null>(null)
  const [place, setPlace] = useState<Place>('home')
  const [picking, setPicking] = useState<'add' | number | null>(null)
  const [forMuscle, setForMuscle] = useState('')
  const [typed, setNote] = useState<string | null>(null) // null: the note Saving will prefills
  const [said, setSaid] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchPlanEdit(controller.signal)
      .then((loaded) => {
        if (loaded === null) return setState({ status: 'signed-out' })
        setState(readyOf(loaded))
        setSlug(loaded.sessions[0]?.slug ?? null)
      })
      .catch(() => setState({ status: 'error' }))
    return () => controller.abort()
  }, [])

  const pending = useMemo(
    () =>
      state.status === 'ready'
        ? changed(state.draft, baselines(state.cycle, state.loaded.sessions))
        : [],
    [state],
  )
  // The cycle is sent only when it differs: without it nothing structural changes (ADR-0093).
  const cycle = useMemo(
    () =>
      state.status === 'ready' && cycleChanged(state.cycle, state.loaded.sessions)
        ? cycleBody(state.cycle)
        : undefined,
    [state],
  )
  const saving = useMemo(
    () => (state.status === 'ready' ? savingWill(state.cycle, state.loaded) : null),
    [state],
  )
  const note = typed ?? saving?.note ?? ''

  // The map follows the draft (program-builder.md F); away has no map, so it shows home's.
  const mapPlace: Place = place === 'gym' ? 'gym' : 'home'
  const [map, setMap] = useState<MapState>({ status: 'loading' })
  const ready = state.status === 'ready'
  const draftKey = JSON.stringify([pending, cycle])
  useEffect(() => {
    if (!ready) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      previewCoverage({ place: mapPlace, versions: pending, cycle }, controller.signal)
        .then((coverage) => setMap(coverage ? { status: 'ready', coverage } : { status: 'hidden' }))
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          const message = err instanceof Error ? err.message : String(err)
          setMap((cur) =>
            cur.status === 'ready' ? { ...cur, problem: message } : { status: 'error', message },
          )
        })
    }, SETTLE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- draftKey stands for the draft
  }, [ready, mapPlace, draftKey])

  if (state.status === 'loading')
    return (
      <AppShell>
        <p className="status" role="status">
          Loading your plan…
        </p>
      </AppShell>
    )
  if (state.status === 'signed-out')
    return (
      <AppShell>
        <SignInCard text="Sign in to edit your plan." />
      </AppShell>
    )
  if (state.status === 'error')
    return (
      <AppShell>
        <RetryCard text="Couldn't load your plan. Check your connection." />
      </AppShell>
    )

  const { loaded, draft } = state
  const session = state.cycle.find((s) => s.slug === slug) ?? state.cycle[0]
  if (!session) return null
  const items = draft[session.slug]![place]
  const cardio = cardioWarning(session.kind, draft[session.slug]!.home, loaded.catalogue)
  const set = (next: EditItem[]) => {
    setSaid(null)
    setState({
      ...state,
      draft: { ...draft, [session.slug]: { ...draft[session.slug]!, [place]: next } },
    })
  }

  const save = async () => {
    setBusy(true)
    setSaid(null)
    try {
      const saved = await savePlanChanges({
        revision: loaded.revision,
        note: note.trim(),
        versions: pending,
        ...(cycle && { cycle }),
      })
      if (saved.status !== 'saved') return setSaid(WHY[saved.reason] ?? saved.reason)
      // A new session being edited reopens under the slug Save gave it.
      if (session.slug.startsWith(NEW)) setSlug(saved.slugs[session.slug.slice(NEW.length)] ?? null)
      const fresh = await fetchPlanEdit()
      if (fresh) setState(readyOf(fresh))
      setNote(null)
      setSaid('Saved as a new version of your plan.')
    } catch (error) {
      setSaid(
        error instanceof SignedOutError
          ? 'Your sign-in ended. Sign in again, then retry.'
          : "That didn't work. Check your connection and try again.",
      )
    } finally {
      setBusy(false)
    }
  }

  const empty =
    place === 'home'
      ? 'No exercises yet.'
      : place === 'gym'
        ? 'Done the same way at the gym.'
        : 'No away version.'
  const next = loaded.sessions.find((s) => s.next)?.slug ?? null
  return (
    <AppShell>
      <h1 className="text-3xl font-extrabold">Edit your plan</h1>
      <p className="m-0">
        Nothing changes until you save. <a href="/plan">Back to your plan</a>
      </p>
      <YourCycle
        cycle={state.cycle}
        next={next}
        onChange={(now) => {
          setSaid(null)
          setState({ ...state, cycle: now })
        }}
        onAdd={(now, entry) => {
          // A copy starts from its session as drafted; an empty one opens the picker at once.
          const from = entry.copyOf ? draft[entry.copyOf]! : { home: [], gym: [], away: [] }
          setSaid(null)
          setState({ ...state, cycle: now, draft: { ...draft, [entry.slug]: from } })
          setSlug(entry.slug)
          setPlace('home')
          setForMuscle('')
          setPicking(entry.copyOf ? null : 'add')
          document.getElementById('edit-items')?.scrollIntoView?.({ behavior: 'smooth' })
        }}
      />
      <section id="edit-items" className={`${card} flex flex-col gap-3`} aria-label="Session">
        <label className="flex flex-col gap-1">
          <span>Session</span>
          <select
            className="min-h-11"
            value={session.slug}
            onChange={(e) => {
              setSlug(e.target.value)
              setPicking(null)
            }}
          >
            {state.cycle.map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Where it's done">
          {PLACES.map((p) => (
            <button
              key={p.place}
              type="button"
              className={small}
              aria-pressed={place === p.place}
              onClick={() => {
                setPlace(p.place)
                setPicking(null)
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
        {cardio && <p className="m-0 text-[var(--bell-ink)]">{cardio}</p>}
        {items.length === 0 ? (
          <p className="m-0 text-[var(--slate)]">{empty}</p>
        ) : (
          <ol className="m-0 flex list-none flex-col gap-2 p-0">
            {items.map((item, at) => (
              <Row
                key={`${item.exercise}-${at}`}
                item={item}
                at={at}
                items={items}
                set={set}
                onSwap={() => setPicking(at)}
              />
            ))}
          </ol>
        )}
        {picking === null ? (
          <button
            type="button"
            className={`${secondary} self-start`}
            onClick={() => {
              setForMuscle('')
              setPicking('add')
            }}
          >
            Add an exercise
          </button>
        ) : (
          <Picker
            catalogue={loaded.catalogue}
            place={place}
            label={picking === 'add' ? 'Add' : `Swap ${items[picking]?.name ?? ''}`}
            key={`${picking}-${forMuscle}`} // a muscle tapped while it's open starts it afresh
            initial={picking === 'add' ? forMuscle : ''}
            onClose={() => setPicking(null)}
            onPick={(from) => {
              set(picking === 'add' ? [...items, newItem(from)] : swapped(items, picking, from))
              setPicking(null)
            }}
          />
        )}
      </section>
      <section className={`${card} flex flex-col gap-3`} aria-labelledby="edit-map">
        <h2 id="edit-map" className="m-0 text-xl font-bold">
          What {days(state.cycle) === 7 ? 'the week' : 'your cycle'} would give each muscle
        </h2>
        <p className="m-0 text-[var(--slate)]">
          It follows your edits. Warnings are for you to weigh: nothing stops you saving.
        </p>
        <BodyMap
          state={map}
          onAdd={(muscle) => {
            setForMuscle(muscle)
            setPicking('add')
            document.getElementById('edit-items')?.scrollIntoView?.({ behavior: 'smooth' })
          }}
        />
      </section>
      <section className={`${card} flex flex-col gap-3`} aria-label="Save">
        {saving && (
          <div aria-labelledby="saving-will" role="group">
            <h2 id="saving-will" className="m-0 text-lg font-bold">
              Saving will
            </h2>
            <ul className="m-0 list-disc pl-5">
              {saving.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        )}
        <label className="flex flex-col gap-1">
          <span>What changed? A short note, for your history.</span>
          <input
            type="text"
            maxLength={120}
            value={note}
            className="min-h-11"
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        <button
          type="button"
          className={`${primaryInline} self-start`}
          disabled={busy || (pending.length === 0 && !cycle) || note.trim() === ''}
          onClick={() => void save()}
        >
          Save as a new version
        </button>
        {said && (
          <p role="status" className="status m-0">
            {said}
          </p>
        )}
      </section>
    </AppShell>
  )
}
