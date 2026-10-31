import { useEffect, useState } from 'react'
import { fetchResidence, type Residence as Found, saveResidence, SignedOutError } from '../api'
import { card } from '../ui'

const ELSEWHERE = 'elsewhere'
export const NOT_FOR_YOU =
  "Training Coach is only for people living in the EU or EEA, so we can't offer it to you."
const names = new Intl.DisplayNames(['en'], { type: 'region' })
const named = (code: string) => names.of(code) ?? code

/** Where the person lives (ADR-0085): a country in the EU or EEA. "Somewhere else" is refused
 * with the reason and nothing is saved. Hidden when it can't be loaded. */
export default function Residence() {
  const [found, setFound] = useState<Found | null>(null)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchResidence(controller.signal)
      .then(setFound)
      .catch(() => {}) // the section stays hidden; the rest of the page still works
    return () => controller.abort()
  }, [])

  if (!found) return null
  const choices = [...found.choices].sort((a, b) => named(a).localeCompare(named(b)))

  const choose = async (code: string) => {
    if (code === ELSEWHERE) return setNote(NOT_FOR_YOU)
    setNote(null)
    try {
      const saved = await saveResidence(code)
      if (typeof saved === 'string') return setNote(saved)
      setFound(saved)
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
    <section aria-labelledby="residence" className={card}>
      <h2 id="residence" className="mb-2 text-xl">
        Where you live
      </h2>
      <label className="flex flex-col gap-1">
        Country
        <select
          value={found.country ?? ''}
          onChange={(e) => void choose(e.target.value)}
          className="min-h-11"
        >
          <option value="" disabled>
            Choose your country
          </option>
          {choices.map((code) => (
            <option key={code} value={code}>
              {named(code)}
            </option>
          ))}
          <option value={ELSEWHERE}>Somewhere else</option>
        </select>
      </label>
      {note && <p role="status">{note}</p>}
    </section>
  )
}
