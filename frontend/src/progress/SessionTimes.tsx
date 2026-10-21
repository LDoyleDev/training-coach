import { useEffect, useState } from 'react'
import { fetchSessionTimes, type SessionTime } from '../api'
import { card } from '../ui'

/**
 * How long each session takes, from the guided sessions timed so far (ADR-0061). Nothing shows
 * until one has been timed, or if it can't be loaded.
 */
export default function SessionTimes() {
  const [found, setFound] = useState<SessionTime[]>([])

  useEffect(() => {
    const abort = new AbortController()
    fetchSessionTimes(abort.signal)
      .then((times) => setFound(times ?? []))
      .catch(() => {}) // the page works without it
    return () => abort.abort()
  }, [])

  if (found.length === 0) return null
  return (
    <section aria-labelledby="times" className={card + ' flex flex-col gap-1'}>
      <h2 id="times" className="m-0 text-xl font-bold">
        How long sessions take
      </h2>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {found.map((t) => (
          <li key={t.session}>
            <span className="font-bold">{t.session}</span>: usually {t.usual} min
            {t.timed > 1 && (
              <span className="text-[var(--slate)]">
                {' '}
                · last {t.last} · fastest {t.fastest} ({t.timed} timed)
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
