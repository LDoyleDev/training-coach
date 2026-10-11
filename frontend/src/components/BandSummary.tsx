import { useEffect, useState } from 'react'
import { type BandHealth, fetchHealth } from '../api'
import { card } from '../ui'
import { hours } from './duration'

const steps = (n: number) => n.toLocaleString('en-GB')
const number = (value: unknown): number | null => (typeof value === 'number' ? value : null)

/**
 * What the band says (ADR-0054), small: last night's sleep, steps and resting heart rate.
 * Nothing shows until band data arrives, or if it can't be loaded.
 */
export default function BandSummary() {
  const [found, setFound] = useState<BandHealth | null>(null)

  useEffect(() => {
    const abort = new AbortController()
    fetchHealth(abort.signal)
      .then(setFound)
      .catch(() => {}) // the page works without it
    return () => abort.abort()
  }, [])

  if (!found) return null
  // Only numbers count: an older server, or anything else, shows nothing rather than break.
  const sleep = typeof found.sleep?.asleep === 'number' ? found.sleep : null
  const steps_today = number(found.steps_today)
  const steps_yesterday = number(found.steps_yesterday)
  const resting = number(found.resting)
  const usual_resting = number(found.usual_resting)
  if (!sleep && steps_today === null && steps_yesterday === null && resting === null) return null
  return (
    <section aria-labelledby="band" className={card + ' flex flex-col gap-1'}>
      <h2 id="band" className="m-0 text-xl font-bold">
        From your band
      </h2>
      {sleep && (
        <p className="m-0">
          Slept {hours(sleep.asleep)}
          <span className="text-[var(--slate)]">
            {' '}
            · deep {hours(sleep.deep)} · REM {hours(sleep.rem)}
          </span>
        </p>
      )}
      {(steps_today !== null || steps_yesterday !== null) && (
        <p className="m-0">
          {steps_today !== null && `${steps(steps_today)} steps today`}
          {steps_today !== null && steps_yesterday !== null && ' · '}
          {steps_yesterday !== null && (
            <span className="text-[var(--slate)]">{steps(steps_yesterday)} yesterday</span>
          )}
        </p>
      )}
      {resting !== null && (
        <p className="m-0">
          Resting heart rate {resting} bpm
          {usual_resting !== null && usual_resting !== resting && (
            <span className="text-[var(--slate)]"> (usually {usual_resting})</span>
          )}
        </p>
      )}
    </section>
  )
}
