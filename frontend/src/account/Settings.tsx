import { type FormEvent, useEffect, useState } from 'react'
import {
  fetchSettings,
  type MessageSettings,
  saveSettings,
  type SettingsChange,
  SignedOutError,
} from '../api'
import { card, primaryInline, secondary } from '../ui'

type TimeKey = 'morning_time' | 'nudge_time' | 'review_time'
type Note = { at: string; text: string }

const TIMES: { key: TimeKey; label: string }[] = [
  { key: 'morning_time', label: 'Morning message' },
  { key: 'nudge_time', label: 'Evening nudge' },
  { key: 'review_time', label: 'Weekly review, Sundays' },
]

const field = 'min-h-11 rounded-xl border-2 border-[var(--line)] px-3'
const row = 'flex flex-wrap items-center gap-2'

function since(day: string): string {
  return new Date(`${day}T12:00:00`).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

/**
 * Everything the bot's /settings changes (ux-flow-plan C6), with the same rules: the server
 * checks each value as the bot would, and a new time moves the bot's messages straight away.
 * Hidden when it can't load, so the rest of Account still works.
 */
export default function Settings() {
  const [prefs, setPrefs] = useState<MessageSettings | null>(null)
  const [times, setTimes] = useState<Record<TimeKey, string> | null>(null)
  const [protein, setProtein] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<Note | null>(null)

  const show = (next: MessageSettings) => {
    setPrefs(next)
    setTimes({
      morning_time: next.morning_time,
      nudge_time: next.nudge_time,
      review_time: next.review_time,
    })
    setProtein(next.protein_g?.toString() ?? '')
  }

  useEffect(() => {
    const controller = new AbortController()
    fetchSettings(controller.signal)
      .then((next) => next && show(next))
      .catch(() => {}) // the section stays hidden
    return () => controller.abort()
  }, [])

  if (!prefs || !times) return null

  const save = async (at: string, change: SettingsChange, done: string, refused: string) => {
    setBusy(true)
    setNote(null)
    try {
      const next = await saveSettings(change)
      if (next === 'invalid') return setNote({ at, text: refused })
      show(next)
      setNote({ at, text: done })
    } catch (error) {
      setNote({
        at,
        text:
          error instanceof SignedOutError
            ? 'Your sign-in ended. Sign in again, then retry.'
            : "That didn't work. Check your connection and try again.",
      })
    } finally {
      setBusy(false)
    }
  }

  const noteAt = (at: string) =>
    note?.at === at && (
      <p role="status" className="status m-0 basis-full">
        {note.text}
      </p>
    )

  const saveProtein = (event: FormEvent) => {
    event.preventDefault()
    const grams = Number(protein)
    void save(
      'protein',
      { protein_g: grams },
      grams ? `Protein target: ${grams} g a day.` : 'Protein target cleared.',
      'Use a whole number of grams between 40 and 400, like 165.',
    )
  }

  const toggle = (at: string, on: boolean, label: [string, string], change: SettingsChange) => (
    <div className={row}>
      <button
        type="button"
        className={secondary}
        disabled={busy}
        onClick={() => save(at, change, 'Saved.', "That couldn't be saved.")}
      >
        {on ? label[1] : label[0]}
      </button>
      {noteAt(at)}
    </div>
  )

  return (
    <section aria-labelledby="settings" className={card + ' flex flex-col gap-4'}>
      <h2 id="settings" className="m-0 text-xl">
        Messages and settings
      </h2>

      {prefs.paused && (
        <p className="m-0 font-bold text-[var(--bell-ink)]">
          Paused: no messages from the bot until you resume.
        </p>
      )}
      {toggle('paused', prefs.paused, ['Pause all messages', 'Resume messages'], {
        paused: !prefs.paused,
      })}

      {TIMES.map(({ key, label }) => (
        <form
          key={key}
          className={row}
          onSubmit={(event) => {
            event.preventDefault()
            void save(
              key,
              { [key]: times[key] },
              `${label}: ${times[key]}.`,
              "That isn't a time like 07:30.",
            )
          }}
        >
          <label htmlFor={key} className="basis-full font-bold">
            {label}
          </label>
          <input
            id={key}
            type="time"
            required
            className={field}
            value={times[key]}
            onChange={(event) => setTimes({ ...times, [key]: event.target.value })}
          />
          <button
            type="submit"
            className={primaryInline}
            disabled={busy || times[key] === prefs[key]}
          >
            Save
          </button>
          {noteAt(key)}
        </form>
      ))}

      <p className="m-0">Evening nudge: {prefs.nudges_enabled ? 'on' : 'off'}</p>
      {toggle('nudges', prefs.nudges_enabled, ['Turn nudges on', 'Turn nudges off'], {
        nudges_enabled: !prefs.nudges_enabled,
      })}

      <p className="m-0">Habit buttons in the evening: {prefs.habits_enabled ? 'on' : 'off'}</p>
      {toggle('habits', prefs.habits_enabled, ['Turn habits on', 'Turn habits off'], {
        habits_enabled: !prefs.habits_enabled,
      })}

      <form className={row} onSubmit={saveProtein}>
        <label htmlFor="protein" className="basis-full font-bold">
          Protein target, grams a day (1.6-2.2 g per kg of bodyweight)
        </label>
        <input
          id="protein"
          type="number"
          inputMode="numeric"
          min={0}
          max={400}
          placeholder="Not set"
          className={field + ' w-28'}
          value={protein}
          onChange={(event) => setProtein(event.target.value)}
        />
        <button
          type="submit"
          className={primaryInline}
          disabled={busy || protein === (prefs.protein_g?.toString() ?? '')}
        >
          Save
        </button>
        {prefs.protein_g !== null && (
          <button
            type="button"
            className={secondary}
            disabled={busy}
            onClick={() =>
              save(
                'protein',
                { protein_g: 0 },
                'Protein target cleared.',
                "That couldn't be saved.",
              )
            }
          >
            Clear
          </button>
        )}
        {noteAt('protein')}
      </form>

      <p className="m-0">
        Training blocks:{' '}
        {prefs.blocks_since
          ? `on since ${since(prefs.blocks_since)} (4 weeks strength, 4 hypertrophy)`
          : 'off'}
      </p>
      {toggle('blocks', prefs.blocks_since !== null, ['Train in blocks', 'Stop training blocks'], {
        blocks: prefs.blocks_since === null,
      })}

      <p className="m-0 text-sm text-[var(--slate)]">Times are {prefs.timezone} time.</p>
    </section>
  )
}
