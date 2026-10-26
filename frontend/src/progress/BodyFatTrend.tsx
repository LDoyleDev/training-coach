import { useEffect, useState } from 'react'
import { type BodyEstimate, fetchBodyFat, type Measurement } from '../api'
import BodyFatChart from '../body/BodyFatChart'
import { card } from '../ui'

/**
 * Body fat on Progress (ADR-0076): the scale's readings and, when it is on, the tape estimate
 * (±4%), as two lines on one axis; no big latest number. Nothing shows until there is a
 * reading, or if it can't be loaded.
 */
export default function BodyFatTrend() {
  const [found, setFound] = useState<{ scale: Measurement[]; estimates: BodyEstimate[] } | null>(
    null,
  )

  useEffect(() => {
    const abort = new AbortController()
    fetchBodyFat(abort.signal)
      .then(setFound)
      .catch(() => {}) // the page works without it
    return () => abort.abort()
  }, [])

  if (!found || (found.scale.length === 0 && found.estimates.length === 0)) return null
  return (
    <section aria-labelledby="body-fat" className={card + ' flex flex-col gap-1'}>
      <h2 id="body-fat" className="m-0 text-xl font-bold">
        Body fat
      </h2>
      <BodyFatChart scale={found.scale} tape={found.estimates} />
    </section>
  )
}
