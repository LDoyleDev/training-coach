import { useEffect, useState, type FormEvent } from 'react'
import {
  fetchCardio,
  fetchSettings,
  saveSettings,
  SignedOutError,
  type CardioOptions,
} from '../api'
import { card, primaryInline } from '../ui'

const PRESETS = [
  { minutes: 0, label: 'None' },
  { minutes: 30, label: '30 min' },
  { minutes: 60, label: '60 min' },
  { minutes: 120, label: '120 min' },
]
const MOST = 600 // minutes a week, as the server allows
const span = (t: readonly number[] | null) => (t ? `${t[0]}–${t[1]} min` : 'none')

type Week = CardioOptions['week']
type Loaded =
  { status: 'loading' | 'hidden' } | { status: 'ready'; extra: number; week: Week | null } // null: targets not refreshed

const choice = (on: boolean) =>
  'min-h-11 rounded-xl border-2 px-3 font-bold disabled:opacity-60 ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

/** Extra cardio a week (ADR-0079): walks or rides outside the plan's sessions. It adds to the
 * zone 2 and the all-cardio targets, which otherwise come from the sessions themselves. */
export default function ExtraCardio() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([fetchSettings(controller.signal), fetchCardio(controller.signal)])
      .then(([prefs, cardio]) =>
        setLoaded(
          prefs && cardio
            ? { status: 'ready', extra: prefs.extra_cardio_min, week: cardio.week }
            : { status: 'hidden' },
        ),
      )
      .catch(() => setLoaded({ status: 'hidden' })) // the plan below still shows
    return () => controller.abort()
  }, [])

  if (loaded.status !== 'ready') return null

  const save = async (minutes: number) => {
    setBusy(true)
    setNote(null)
    try {
      const saved = await saveSettings({ extra_cardio_min: minutes })
      if (saved === 'invalid') return setNote(`A number from 0 to ${MOST}.`)
      // Saved: show it now, whatever the targets' refresh does next (review of #391).
      const extra = saved.extra_cardio_min
      setLoaded({ status: 'ready', extra, week: null })
      setTyped('')
      setNote(extra ? `Saved: ${extra} min a week.` : 'Saved: none.')
      const cardio = await fetchCardio().catch(() => null)
      setLoaded({ status: 'ready', extra, week: cardio ? cardio.week : null })
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

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const minutes = Number(typed)
    if (!Number.isInteger(minutes) || minutes < 0 || minutes > MOST)
      return setNote(`A number from 0 to ${MOST}.`)
    void save(minutes)
  }

  const { extra, week } = loaded
  return (
    <section aria-labelledby="extra-cardio" className={`${card} flex flex-col gap-3`}>
      <h2 id="extra-cardio" className="m-0 text-xl font-bold">
        Extra cardio a week
      </h2>
      <p className="m-0 text-[var(--slate)]">
        Walks or rides outside the sessions. They add to your zone 2 and cardio targets.
      </p>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Extra cardio a week">
        {PRESETS.map(({ minutes, label }) => (
          <button
            key={minutes}
            type="button"
            aria-pressed={extra === minutes}
            className={choice(extra === minutes)}
            disabled={busy}
            onClick={() => extra !== minutes && void save(minutes)}
          >
            {label}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1">
          <span>Or minutes a week</span>
          <input
            type="text"
            inputMode="numeric"
            value={typed}
            placeholder={PRESETS.some((p) => p.minutes === extra) ? '' : String(extra)}
            onChange={(e) => setTyped(e.target.value)}
            className="min-h-11 w-28 text-lg"
          />
        </label>
        <button type="submit" className={primaryInline} disabled={busy || typed === ''}>
          Save
        </button>
      </form>
      {note && (
        <p role="status" className="status m-0">
          {note}
        </p>
      )}
      {week ? (
        <p className="m-0">
          Targets for 7 days: zone 2 {span(week.zone2_target)}, all cardio {span(week.total_target)}
          .
        </p>
      ) : (
        !busy && (
          <p className="m-0 text-[var(--slate)]">
            Couldn't refresh the targets. Reload the page to see them.
          </p>
        )
      )}
    </section>
  )
}
