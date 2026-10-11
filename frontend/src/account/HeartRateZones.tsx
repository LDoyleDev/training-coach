import { type FormEvent, useEffect, useState } from 'react'
import { fetchHeartRate, type HeartRate, saveHeartRate, SignedOutError } from '../api'
import { card, primaryInline } from '../ui'

const NAMES = ['Very easy', 'Easy (zone 2)', 'Moderate', 'Hard', 'Max']

const number = (text: string): number | null => (text.trim() ? Number(text) : null)

function source(hr: HeartRate): string {
  if (hr.own_max !== null) return 'your own number'
  if (hr.peak !== null && hr.peak === hr.max) return 'the highest a workout reached'
  if (hr.estimated_max !== null) return '208 − 0.7 × your age'
  return 'a default, until you add your birth year'
}

/**
 * Heart-rate zones (ADR-0055): Karvonen zones from resting heart rate (last week's nights) and
 * max heart rate (own number, else estimated from age and raised by hard workouts). Imported
 * workouts count minutes in these zones.
 */
export default function HeartRateZones() {
  const [hr, setHr] = useState<HeartRate | null>(null)
  const [year, setYear] = useState('')
  const [own, setOwn] = useState('')
  const [note, setNote] = useState<string | null>(null)

  const show = (found: HeartRate) => {
    setHr(found)
    setYear(found.birth_year?.toString() ?? '')
    setOwn(found.own_max?.toString() ?? '')
  }

  useEffect(() => {
    const controller = new AbortController()
    fetchHeartRate(controller.signal)
      .then((found) => found && show(found))
      .catch(() => {}) // the section stays hidden; the rest of the page still works
    return () => controller.abort()
  }, [])

  if (!hr) return null

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setNote(null)
    try {
      const saved = await saveHeartRate({ birth_year: number(year), own_max: number(own) })
      if (typeof saved === 'string') return setNote(saved)
      show(saved)
      setNote('Saved.')
    } catch (error) {
      setNote(
        error instanceof SignedOutError
          ? 'Your sign-in ended. Sign in again, then retry.'
          : "That didn't work. Check your connection and try again.",
      )
    }
  }

  return (
    <section aria-labelledby="heart-rate" className={card}>
      <h2 id="heart-rate" className="mb-2 text-xl">
        Heart-rate zones
      </h2>
      <p>
        Resting {hr.rest} bpm, max {hr.max} bpm (from {source(hr)}).
      </p>
      <ul className="my-2">
        {hr.zones.map((z) => (
          <li
            key={z.zone}
            className="flex justify-between gap-2 border-b border-[var(--line)] py-1"
          >
            <span>
              {z.zone}. {NAMES[z.zone - 1]}
            </span>
            <span>
              {z.low}–{z.high} bpm
            </span>
          </li>
        ))}
      </ul>
      <form onSubmit={(e) => void save(e)} className="flex flex-col gap-2">
        <label className="flex flex-col gap-1">
          Birth year (for the max estimate)
          <input
            inputMode="numeric"
            value={year}
            onChange={(e) => setYear(e.target.value.replace(/\D/g, ''))}
            placeholder="1990"
          />
        </label>
        <label className="flex flex-col gap-1">
          Your own max heart rate, if you know it
          <input
            inputMode="numeric"
            value={own}
            onChange={(e) => setOwn(e.target.value.replace(/\D/g, ''))}
            placeholder="leave empty to estimate"
          />
        </label>
        <p>
          <button type="submit" className={primaryInline}>
            Save
          </button>
        </p>
      </form>
      {note && <p role="status">{note}</p>}
    </section>
  )
}
