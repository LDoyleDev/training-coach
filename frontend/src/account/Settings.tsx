import { type FormEvent, useEffect, useState } from 'react'
import {
  fetchSettings,
  type MessageSettings,
  saveSettings,
  type SettingsChange,
  SignedOutError,
} from '../api'
import { type Sound, playChange, unlockAudio } from '../hiit/sounds'
import { card, primaryInline, secondary } from '../ui'
import { LAST_SET, LAST_SET_LINE, LAST_SET_LOCKED } from '../session/safety'

type TimeKey = 'morning_time' | 'nudge_time' | 'review_time'
type Pace = MessageSettings['pace']
type Places = MessageSettings['places']
type SessionMinutes = MessageSettings['session_minutes']
type Note = { at: string; text: string }

const TIMES: { key: TimeKey; label: string }[] = [
  { key: 'morning_time', label: 'Morning message' },
  { key: 'nudge_time', label: 'Evening nudge' },
  { key: 'review_time', label: 'Weekly review, Sundays' },
]

/** How much each set aims for next time (ADR-0057); the bot's /settings uses the same words. */
const PACES: { pace: Pace; label: string; line: string }[] = [
  { pace: 'steady', label: 'Steady', line: 'One rep at a time.' },
  { pace: 'standard', label: 'Standard', line: 'About a tenth of the range at a time.' },
  { pace: 'fast', label: 'Fast', line: 'At least two reps at a time.' },
]

/** Where the person trains (ADR-0071): a gym has everything, home has the kit they list. */
const PLACES: { places: Places; label: string; line: string }[] = [
  { places: 'home', label: 'Home', line: 'With the kit you list under My equipment.' },
  { places: 'gym', label: 'Gym', line: 'A gym has everything.' },
  { places: 'both', label: 'Both', line: 'You pick home or gym on the day.' },
]

type AvoidKey = 'avoid_floor' | 'avoid_kneeling' | 'avoid_impact' | 'avoid_hanging' | 'avoid_knees'

/** What the person would rather avoid (ADR-0083): each locks the ladder steps that need it, as
 * missing kit does. Preferences, not medical: no reason is asked or kept. */
const AVOID: { key: AvoidKey; label: string }[] = [
  { key: 'avoid_floor', label: 'Keep me off the floor' },
  { key: 'avoid_kneeling', label: 'No kneeling' },
  { key: 'avoid_impact', label: 'No jumping or running' },
  { key: 'avoid_hanging', label: 'No hanging' },
  { key: 'avoid_knees', label: 'Easy on my knees' },
]

/** Minutes per session (ADR-0082): the same lengths as Short on time today on the session. */
const LENGTHS: { minutes: SessionMinutes; label: string }[] = [
  { minutes: null, label: 'As planned' },
  { minutes: 40, label: '40 min' },
  { minutes: 30, label: '30 min' },
  { minutes: 20, label: '20 min' },
]

/**
 * What every guided timer plays at each change (ADR-0062), in the order shown: the boxing bell,
 * everyone's default, first (ADR-0074). A record, so a new sound can't be left out.
 */
const SOUND_LABELS: Record<Sound, string> = {
  ring: 'Boxing bell',
  chime: 'Chime',
  beep: 'Beep',
  wood: 'Wood block',
  bell: 'Bell',
  none: 'No sound',
}
const SOUNDS = Object.entries(SOUND_LABELS).map(([sound, label]) => ({
  sound: sound as Sound,
  label,
}))

/** A sound's switch and next-movement change, a moment apart, to hear before choosing. */
function preview(sound: Sound) {
  unlockAudio() // inside the tap: browsers only allow sound after a gesture
  playChange(sound, 'switch')
  window.setTimeout(() => playChange(sound, 'next'), 900)
}

const choice = (on: boolean) =>
  'min-h-11 w-full rounded-xl border-2 px-4 py-2 text-left font-bold disabled:opacity-60 ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

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

      <p className="m-0">
        Use the talk test, not heart-rate zones: {prefs.talk_test ? 'on' : 'off'}
      </p>
      <p className="m-0 text-sm text-[var(--slate)]">
        Cardio effort then shows as how well you can talk: easy, you can sing; moderate, full
        sentences; hard, only a few words. Your logs and totals stay the same. Heart rate can be a
        poor guide for some people, for example with some heart medicines or heart rhythms. The talk
        test works for everyone.
      </p>
      {toggle('talk', prefs.talk_test, ['Use the talk test', 'Use heart-rate zones'], {
        talk_test: !prefs.talk_test,
      })}

      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 font-bold">What you'd rather avoid</legend>
        <p className="m-0 text-sm text-[var(--slate)]">
          You choose what you're ready for. These skip steps that need it.
        </p>
        {AVOID.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            aria-pressed={prefs[key]}
            className={choice(prefs[key])}
            disabled={busy}
            onClick={() =>
              save(
                'avoid',
                { [key]: !prefs[key] },
                `${label}: ${prefs[key] ? 'off' : 'on'}.`,
                "That couldn't be saved.",
              )
            }
          >
            {label}
            <span className="block font-normal">{prefs[key] ? 'On' : 'Off'}</span>
          </button>
        ))}
        {noteAt('avoid')}
      </fieldset>
      <p className="m-0">
        {LAST_SET}. {prefs.last_set_amrap ? 'On' : 'Off'}.
      </p>
      <p className="m-0 text-sm text-[var(--slate)]">{LAST_SET_LINE}</p>
      {prefs.last_set_locked && !prefs.last_set_amrap ? (
        <p className="m-0 font-bold">{LAST_SET_LOCKED}</p>
      ) : (
        <div className={row}>
          <button
            type="button"
            className={secondary}
            disabled={busy}
            onClick={() =>
              save(
                'last-set',
                { last_set_amrap: !prefs.last_set_amrap },
                'Saved.',
                `${LAST_SET_LOCKED}.`,
              )
            }
          >
            {prefs.last_set_amrap ? 'Turn the last set off' : 'Turn the last set on'}
          </button>
          {noteAt('last-set')}
        </div>
      )}

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

      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 font-bold">Where you train</legend>
        {PLACES.map(({ places, label, line }) => (
          <button
            key={places}
            type="button"
            aria-pressed={prefs.places === places}
            className={choice(prefs.places === places)}
            disabled={busy}
            onClick={() =>
              prefs.places !== places &&
              save(
                'places',
                { places },
                `Where you train: ${label.toLowerCase()}.`,
                "That couldn't be saved.",
              )
            }
          >
            {label}
            <span className="block font-normal">{line}</span>
          </button>
        ))}
        {noteAt('places')}
      </fieldset>

      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 font-bold">Time per session</legend>
        <p className="m-0 text-sm text-[var(--slate)]">
          Every session runs at this length unless you pick another for the day.
        </p>
        <div className="grid grid-cols-2 gap-2">
          {LENGTHS.map(({ minutes, label }) => (
            <button
              key={label}
              type="button"
              aria-pressed={prefs.session_minutes === minutes}
              className={choice(prefs.session_minutes === minutes)}
              disabled={busy}
              onClick={() =>
                prefs.session_minutes !== minutes &&
                save(
                  'minutes',
                  { session_minutes: minutes },
                  `Time per session: ${label.toLowerCase()}.`,
                  "That couldn't be saved.",
                )
              }
            >
              {label}
            </button>
          ))}
        </div>
        {noteAt('minutes')}
      </fieldset>

      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 font-bold">Pace: how much each set aims for next time</legend>
        {PACES.map(({ pace, label, line }) => (
          <button
            key={pace}
            type="button"
            aria-pressed={prefs.pace === pace}
            className={choice(prefs.pace === pace)}
            disabled={busy}
            onClick={() =>
              prefs.pace !== pace &&
              save('pace', { pace }, `Pace: ${label.toLowerCase()}.`, "That couldn't be saved.")
            }
          >
            {label}
            <span className="block font-normal">{line}</span>
          </button>
        ))}
        {noteAt('pace')}
      </fieldset>

      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 font-bold">Timer sound</legend>
        <p className="m-0 text-sm text-[var(--slate)]">
          Every guided timer plays it: when a rest ends, and at each change in the mobility flow and
          guided stretching.
        </p>
        <div className="grid grid-cols-2 gap-2">
          {SOUNDS.map(({ sound, label }) => (
            <button
              key={sound}
              type="button"
              aria-pressed={prefs.sound === sound}
              className={choice(prefs.sound === sound)}
              disabled={busy}
              onClick={() => {
                if (sound !== 'none') preview(sound)
                if (prefs.sound !== sound)
                  save(
                    'sound',
                    { sound },
                    `Timer sound: ${label.toLowerCase()}.`,
                    "That couldn't be saved.",
                  )
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="m-0 text-sm text-[var(--slate)]">
          Tap one to hear it. The phone also buzzes where it can.
        </p>
        {noteAt('sound')}
      </fieldset>

      <p className="m-0 text-sm text-[var(--slate)]">Times are {prefs.timezone} time.</p>
    </section>
  )
}
