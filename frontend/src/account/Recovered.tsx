import { useEffect, useState } from 'react'
import { fetchMe } from '../api'
import { card } from '../ui'

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })

/**
 * After a recovery with the admin's link (ADR-0059): said on Account for 30 days, with no way to
 * dismiss it, so an admin who signed in that way can't hide it.
 */
export default function Recovered() {
  const [at, setAt] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchMe(controller.signal)
      .then((me) => setAt(me?.recovered_by_admin_at ?? null))
      .catch(() => {}) // the rest of the page still works
    return () => controller.abort()
  }, [])

  if (!at) return null
  return (
    <section aria-labelledby="recovered" className={card}>
      <h2 id="recovered" className="mb-2 text-xl">
        Recovered by the admin
      </h2>
      <p className="m-0">
        Your account was recovered with a link from the admin on {day(at)}. Every other device was
        signed out and every passkey removed then. If that wasn&apos;t you, tell the admin.
      </p>
    </section>
  )
}
