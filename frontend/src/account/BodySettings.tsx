import { type FormEvent, useEffect, useState } from 'react'
import {
  type BodySettings as Found,
  fetchBodySettings,
  saveBodySettings,
  SignedOutError,
} from '../api'
import { ESTIMATE } from '../body/BodyFatChart'
import { card, primaryInline } from '../ui'

type Choice = Found['body_fat_estimate']

const number = (text: string): number | null => (text.trim() ? Number(text) : null)

/**
 * Body settings (ADR-0076): the height the tape estimate needs, where the thigh is measured,
 * and whether the body-fat estimate is worked out. Hidden when it can't be loaded.
 */
export default function BodySettings() {
  const [found, setFound] = useState<Found | null>(null)
  const [height, setHeight] = useState('')
  const [thigh, setThigh] = useState('')
  const [estimate, setEstimate] = useState<Choice>('off')
  const [note, setNote] = useState<string | null>(null)

  const show = (settings: Found) => {
    setFound(settings)
    setHeight(settings.height_cm?.toString() ?? '')
    setThigh(settings.thigh_offset_cm.toString())
    setEstimate(settings.body_fat_estimate)
  }

  useEffect(() => {
    const controller = new AbortController()
    fetchBodySettings(controller.signal)
      .then((settings) => settings && show(settings))
      .catch(() => {}) // the section stays hidden; the rest of the page still works
    return () => controller.abort()
  }, [])

  if (!found) return null

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setNote(null)
    const offset = number(thigh)
    if (offset === null) return setNote('Say how far above the kneecap you measure the thigh.')
    try {
      const saved = await saveBodySettings({
        height_cm: number(height),
        thigh_offset_cm: offset,
        body_fat_estimate: estimate,
      })
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
    <section aria-labelledby="body-settings" className={card}>
      <h2 id="body-settings" className="mb-2 text-xl">
        Body
      </h2>
      <form onSubmit={(e) => void save(e)} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          Height (cm)
          <input
            inputMode="numeric"
            value={height}
            onChange={(e) => setHeight(e.target.value.replace(/\D/g, ''))}
            placeholder="180"
          />
        </label>
        <label className="flex flex-col gap-1">
          Thigh: cm above the top of the kneecap
          <input
            inputMode="numeric"
            value={thigh}
            onChange={(e) => setThigh(e.target.value.replace(/\D/g, ''))}
          />
          <span className="text-sm text-[var(--slate)]">
            The same spot every time, so a change is your thigh, not the tape. Usually 15.
          </span>
        </label>
        <fieldset className="m-0 flex flex-col gap-1 border-0 p-0">
          <legend className="mb-1">Body-fat estimate from tape</legend>
          <label className="flex min-h-11 items-center gap-2">
            <input
              type="radio"
              name="body-fat-estimate"
              checked={estimate === 'off'}
              onChange={() => setEstimate('off')}
            />
            Off
          </label>
          <label className="flex min-h-11 items-center gap-2">
            <input
              type="radio"
              name="body-fat-estimate"
              checked={estimate === 'navy_male'}
              onChange={() => setEstimate('navy_male')}
            />
            On (US Navy formula for men)
          </label>
          <span className="text-sm text-[var(--slate)]">
            An {ESTIMATE}. It needs your height, and a waist and a neck measured on the same day.
          </span>
          {estimate === 'navy_male' && height === '' && (
            <span className="text-sm font-bold">Add your height to see it.</span>
          )}
        </fieldset>
        <p className="m-0">
          <button type="submit" className={primaryInline}>
            Save
          </button>
        </p>
      </form>
      {note && <p role="status">{note}</p>}
    </section>
  )
}
