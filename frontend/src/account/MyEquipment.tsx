import { type FormEvent, useCallback, useEffect, useState } from 'react'
import {
  type Equipment,
  fetchEquipment,
  fetchUnlocks,
  type KitItem,
  type KitItemBody,
  type KitKind,
  type KitUnlocks,
  saveEquipment,
  SignedOutError,
} from '../api'
import { moveHref } from '../plan/ladder'
import { actions, card, primaryInline, secondary, small } from '../ui'
import {
  blank,
  bodyFromItem,
  bodyOf,
  type Draft,
  draftOf,
  HINTS,
  placeholder,
  RESISTANCES,
  STABLE,
  token,
} from './kit'

type Loaded =
  | { status: 'loading' }
  | { status: 'hidden' } // signed out: the page says so
  | { status: 'error' }
  | { status: 'ready'; kit: Equipment }

/** Which item the form is for: a new one, or the saved one at `index`. */
type Editing = { draft: Draft; index: number | null }

const FAILED = "That didn't work. Nothing was saved; check your connection and try again."
const SIGNED_OUT = 'Your sign-in ended. Sign in again, then retry.'

/**
 * My equipment (ADR-0071): the home kit, tap to add, with what each item unlocks before it's
 * added. Saved as the whole list. No kit listed: nothing is locked; a saved empty list is
 * bodyweight only.
 */
export default function MyEquipment() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [editing, setEditing] = useState<Editing | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [refused, setRefused] = useState<string | null>(null)

  const load = useCallback((signal?: AbortSignal) => {
    fetchEquipment(signal)
      .then((kit) => setLoaded(kit ? { status: 'ready', kit } : { status: 'hidden' }))
      .catch(() => {
        if (!signal?.aborted) setLoaded({ status: 'error' })
      })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  useEffect(() => {
    if (loaded.status === 'ready' && window.location.hash === '#my-equipment')
      document.getElementById('my-equipment')?.scrollIntoView?.({ block: 'start' })
  }, [loaded.status])

  if (loaded.status === 'hidden') return null

  const save = async (items: KitItemBody[], done: string) => {
    setBusy(true)
    setNote(null)
    setRefused(null)
    try {
      const saved = await saveEquipment(items)
      if (typeof saved === 'string') return setRefused(saved)
      setLoaded({ status: 'ready', kit: saved })
      setEditing(null)
      setNote(done)
    } catch (error) {
      setRefused(error instanceof SignedOutError ? SIGNED_OUT : FAILED)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      id="my-equipment"
      aria-labelledby="my-equipment-title"
      className={card + ' flex scroll-mt-4 flex-col gap-3'}
    >
      <h2 id="my-equipment-title" className="m-0 text-xl">
        My equipment
      </h2>
      {loaded.status === 'loading' && (
        <p className="status m-0" role="status">
          Loading your kit…
        </p>
      )}
      {loaded.status === 'error' && (
        <>
          <p className="status-error m-0" role="alert">
            Couldn't load your kit. Check your connection.
          </p>
          <button
            type="button"
            className="self-start"
            onClick={() => {
              setLoaded({ status: 'loading' })
              load()
            }}
          >
            Try again
          </button>
        </>
      )}
      {loaded.status === 'ready' && (
        <Ready
          kit={loaded.kit}
          editing={editing}
          setEditing={(e) => {
            setRefused(null)
            setNote(null)
            setEditing(e)
          }}
          busy={busy}
          refused={refused}
          save={(items, done) => void save(items, done)}
        />
      )}
      {note && (
        <p className="m-0" role="status">
          {note}
        </p>
      )}
    </section>
  )
}

function Ready({
  kit,
  editing,
  setEditing,
  busy,
  refused,
  save,
}: {
  kit: Equipment
  editing: Editing | null
  setEditing: (e: Editing | null) => void
  busy: boolean
  refused: string | null
  save: (items: KitItemBody[], done: string) => void
}) {
  const bodies = kit.items.map(bodyFromItem)
  const names = new Map(kit.kinds.map((k) => [k.kit, k.name]))
  const name = (k: KitKind) => names.get(k) ?? k

  return (
    <>
      {!kit.listed ? (
        <>
          <p className="m-0">
            <strong>No kit listed: nothing is locked.</strong> Every step stays open until you list
            what you have at home. Then a step that needs something you don't list shows as locked;
            you can still choose it by hand.
          </p>
          <button
            type="button"
            className={secondary + ' self-start'}
            disabled={busy}
            onClick={() => save([], 'Saved: bodyweight only.')}
          >
            I have no kit: bodyweight only
          </button>
        </>
      ) : kit.items.length === 0 ? (
        <p className="m-0">
          <strong>Bodyweight only.</strong> Steps that need kit show as locked; you can still choose
          them by hand. Add what you have below.
        </p>
      ) : (
        <>
          <p className="m-0">
            Steps that need something not on this list show as locked; you can still choose them by
            hand.
          </p>
          <ul className="m-0 list-none p-0">
            {kit.items.map((item, i) => (
              <ItemRow
                key={token(bodies[i])}
                item={item}
                busy={busy}
                onEdit={() => setEditing({ draft: draftOf(item), index: i })}
                onRemove={() =>
                  save(
                    bodies.filter((_, j) => j !== i),
                    kit.items.length === 1
                      ? `Removed ${item.label}. Saved: bodyweight only.`
                      : `Removed ${item.label}.`,
                  )
                }
              />
            ))}
          </ul>
        </>
      )}

      {editing ? (
        <ItemForm
          key={`${editing.index ?? 'new'} ${editing.draft.kit}`}
          editing={editing}
          original={editing.index === null ? null : bodies[editing.index]}
          kindName={name(editing.draft.kit)}
          busy={busy}
          refused={refused}
          onCancel={() => setEditing(null)}
          onSave={(body) => {
            const items =
              editing.index === null
                ? [...bodies, body]
                : bodies.map((b, j) => (j === editing.index ? body : b))
            save(items, editing.index === null ? 'Added to your kit.' : 'Saved.')
          }}
        />
      ) : (
        <div className="flex flex-col gap-2">
          <h3 className="m-0 text-base font-bold">Tap to add</h3>
          <div className={actions}>
            {kit.kinds.map((k) => (
              <button
                key={k.kit}
                type="button"
                className={small}
                disabled={busy}
                onClick={() => setEditing({ draft: blank(k.kit), index: null })}
              >
                + {k.name}
              </button>
            ))}
          </div>
          {refused && (
            <p className="status-error m-0" role="alert">
              {refused}
            </p>
          )}
        </div>
      )}
    </>
  )
}

function ItemRow({
  item,
  busy,
  onEdit,
  onRemove,
}: {
  item: KitItem
  busy: boolean
  onEdit: () => void
  onRemove: () => void
}) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] py-2 last:border-0">
      <span className="flex flex-col">
        <span className="font-bold">{item.label}</span>
        {item.note && <span className="text-[var(--slate)]">{item.note}</span>}
        {item.kit === 'bench' && <span>{STABLE}</span>}
      </span>
      <span className={actions}>
        <button
          type="button"
          className={small}
          disabled={busy}
          onClick={onEdit}
          aria-label={`Edit ${item.label}`}
        >
          Edit
        </button>
        <button
          type="button"
          className={small}
          disabled={busy}
          onClick={onRemove}
          aria-label={`Remove ${item.label}`}
        >
          Remove
        </button>
      </span>
    </li>
  )
}

function ItemForm({
  editing,
  original,
  kindName,
  busy,
  refused,
  onCancel,
  onSave,
}: {
  editing: Editing
  original: KitItemBody | null
  kindName: string
  busy: boolean
  refused: string | null
  onCancel: () => void
  onSave: (body: KitItemBody) => void
}) {
  const [draft, setDraft] = useState(editing.draft)
  const set = (change: Partial<Draft>) => setDraft((cur) => ({ ...cur, ...change }))
  const body = bodyOf(draft)
  const asked = body ? token(body) : null
  // Changing only the note opens nothing new, so there is nothing to ask.
  const preview = asked !== null && asked !== (original ? token(original) : null) ? asked : null
  const hint = HINTS[draft.kit]
  const adding = editing.index === null

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (body) onSave(body)
  }

  return (
    <form onSubmit={submit}>
      <fieldset className="m-0 flex flex-col gap-3 rounded-xl border-2 border-[var(--line)] p-3">
        <legend className="px-1 font-bold">
          {adding ? `Add: ${kindName}` : `Edit: ${kindName}`}
        </legend>
        {hint && <p className="m-0">{hint}</p>}

        {draft.kit === 'dumbbells' && (
          <div className="flex flex-col gap-1">
            {[
              [false, 'A fixed pair'],
              [true, 'Adjustable, with a range'],
            ].map(([value, text]) => (
              <label key={String(value)} className="flex min-h-11 items-center gap-3">
                <input
                  type="radio"
                  name="dumbbells"
                  className="size-5"
                  checked={draft.adjustable === value}
                  onChange={() => set({ adjustable: value as boolean })}
                />
                {text}
              </label>
            ))}
          </div>
        )}
        {draft.kit === 'dumbbells' && draft.adjustable && (
          <Kg label="Lightest (kg)" value={draft.minKg} onChange={(minKg) => set({ minKg })} />
        )}
        {draft.kit === 'kettlebell' && (
          <Kg label="Weight (kg)" value={draft.kg} onChange={(kg) => set({ kg })} />
        )}
        {draft.kit === 'dumbbells' && (
          <Kg
            label={draft.adjustable ? 'Heaviest (kg)' : 'Each dumbbell (kg)'}
            value={draft.kg}
            onChange={(kg) => set({ kg })}
          />
        )}
        {draft.kit === 'backpack' && (
          <Kg label="Loads up to (kg)" value={draft.kg} onChange={(kg) => set({ kg })} />
        )}
        {draft.kit === 'band' && (
          <div className="flex flex-col gap-1" role="radiogroup" aria-label="How strong">
            {RESISTANCES.map((r) => (
              <label key={r} className="flex min-h-11 items-center gap-3">
                <input
                  type="radio"
                  name="resistance"
                  className="size-5"
                  checked={draft.resistance === r}
                  onChange={() => set({ resistance: r })}
                />
                {r[0].toUpperCase() + r.slice(1)}
              </label>
            ))}
          </div>
        )}
        <label className="flex flex-col gap-1">
          Note (optional)
          <input
            value={draft.note}
            maxLength={40}
            placeholder={placeholder(draft.kit)}
            onChange={(e) => set({ note: e.target.value })}
          />
        </label>

        {preview && <Unlocks add={preview} />}
        {refused && (
          <p className="status-error m-0" role="alert">
            {refused}
          </p>
        )}
        <div className={actions}>
          <button type="submit" className={primaryInline} disabled={busy || body === null}>
            {adding ? 'Add to my kit' : 'Save changes'}
          </button>
          <button type="button" className={secondary} onClick={onCancel}>
            Cancel
          </button>
        </div>
      </fieldset>
    </form>
  )
}

function Kg({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="flex flex-col gap-1">
      {label}
      <input
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/[^\d.,]/g, ''))}
      />
    </label>
  )
}

type Preview =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'refused'; reason: string }
  | { status: 'ready'; found: KitUnlocks }

type Answer = Exclude<Preview, { status: 'loading' }> & { add: string }

/** What the item would open, asked again as it changes ("16 kg kettlebell: 4 new steps"). */
function Unlocks({ add }: { add: string }) {
  const [answer, setAnswer] = useState<Answer | null>(null)
  // An answer for an earlier value is stale: show "checking" until this one's arrives.
  const preview: Preview = answer?.add === add ? answer : { status: 'loading' }

  useEffect(() => {
    const controller = new AbortController()
    fetchUnlocks(add, controller.signal)
      .then((found) =>
        setAnswer(
          typeof found === 'string'
            ? { add, status: 'refused', reason: found }
            : { add, status: 'ready', found },
        ),
      )
      .catch(() => {
        if (!controller.signal.aborted) setAnswer({ add, status: 'error' })
      })
    return () => controller.abort()
  }, [add])

  return (
    <div aria-live="polite" className="flex flex-col gap-1">
      {preview.status === 'loading' && <p className="m-0">Checking what it unlocks…</p>}
      {preview.status === 'error' && (
        <p className="m-0">Couldn't check what it unlocks. You can still add it.</p>
      )}
      {preview.status === 'refused' && <p className="status-error m-0">{preview.reason}</p>}
      {preview.status === 'ready' && (
        <>
          <p className="m-0 font-bold">{preview.found.summary}</p>
          {preview.found.steps.length > 0 && (
            <ul className="m-0 flex flex-col gap-1 pl-6">
              {preview.found.steps.map((s) => (
                <li key={`${s.slug} ${s.step}`}>
                  <a href={moveHref(s.slug)} className="font-bold underline">
                    {s.exercise}
                  </a>
                  : {s.step}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
