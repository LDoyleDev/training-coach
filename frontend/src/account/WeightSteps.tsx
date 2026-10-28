import { type FormEvent, useEffect, useState } from 'react'
import { fetchSettings, type MessageSettings, saveSettings, SignedOutError } from '../api'
import { card, primaryInline } from '../ui'

type Steps = MessageSettings['increments']
type Kit = keyof Steps
type Loaded = { status: 'loading' | 'hidden' } | { status: 'ready'; steps: Steps; defaults: Steps }

const KITS: { kit: Kit; label: string }[] = [
  { kit: 'barbell', label: 'Barbell' },
  { kit: 'dumbbells', label: 'Dumbbells, each' },
  { kit: 'machine', label: 'Machine or cable' },
]
const WRONG = 'From 0.25 to 20 kg, in steps of 0.25.'
const blank: Record<Kit, string> = { barbell: '', dumbbells: '', machine: '' }

/** A typed step in kg, or null unless it is one the server takes. A decimal comma is fine. */
function typedStep(text: string): number | null {
  const found = text.trim().replace(',', '.')
  if (!/^\d{1,2}(\.\d{1,2})?$/.test(found)) return null
  const kg = Number(found)
  return kg >= 0.25 && kg <= 20 && Number.isInteger(kg * 4) ? kg : null
}

/**
 * Weight steps (ADR-0072): each person's smallest step for each kit, in place of the defaults.
 * − and + on the set screen move by it, and the suggested next weight adds it.
 */
export default function WeightSteps() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [typed, setTyped] = useState(blank)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchSettings(controller.signal)
      .then((prefs) =>
        setLoaded(
          prefs
            ? { status: 'ready', steps: prefs.increments, defaults: prefs.default_increments }
            : { status: 'hidden' },
        ),
      )
      .catch(() => setLoaded({ status: 'hidden' })) // the rest of Account still works
    return () => controller.abort()
  }, [])

  if (loaded.status !== 'ready') return null

  const changed = KITS.filter(({ kit }) => typed[kit].trim() !== '')
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const steps = changed.map(({ kit }) => [kit, typedStep(typed[kit])] as const)
    if (steps.length === 0 || steps.some(([, kg]) => kg === null)) return setNote(WRONG)
    setBusy(true)
    setNote(null)
    try {
      const saved = await saveSettings({ increments: Object.fromEntries(steps) })
      if (saved === 'invalid') return setNote(WRONG)
      setLoaded({ status: 'ready', steps: saved.increments, defaults: saved.default_increments })
      setTyped(blank)
      setNote('Saved.')
    } catch (error) {
      setNote(
        error instanceof SignedOutError
          ? 'Your sign-in ended. Sign in again, then retry.'
          : "That didn't work. Check your connection and try again.",
      )
    } finally {
      setBusy(false)
    }
  }

  const { steps, defaults } = loaded
  return (
    <section aria-labelledby="weight-steps" className={`${card} flex flex-col gap-3`}>
      <h2 id="weight-steps" className="m-0 text-xl">
        Weight steps
      </h2>
      <p className="m-0 text-[var(--slate)]">
        The smallest step your weights go up or down by. − and + on the set screen move by it, and
        the next weight suggested adds it.
      </p>
      <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-3">
        {KITS.map(({ kit, label }) => (
          <label key={kit} className="flex flex-wrap items-center gap-2">
            <span className="min-w-40 font-bold">{label}</span>
            <input
              type="text"
              inputMode="decimal"
              value={typed[kit]}
              placeholder={String(steps[kit])}
              onChange={(e) => setTyped({ ...typed, [kit]: e.target.value })}
              className="min-h-11 w-24 rounded-xl border-2 border-[var(--line)] px-3 text-lg"
            />
            <span>kg</span>
            <span className="text-sm text-[var(--slate)]">
              {steps[kit] === defaults[kit] ? 'the default' : `default ${defaults[kit]} kg`}
            </span>
          </label>
        ))}
        <button
          type="submit"
          className={`${primaryInline} self-start`}
          disabled={busy || changed.length === 0}
        >
          Save
        </button>
      </form>
      {note && (
        <p role="status" className="status m-0">
          {note}
        </p>
      )}
    </section>
  )
}
