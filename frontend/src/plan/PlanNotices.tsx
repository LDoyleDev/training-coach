import { useEffect, useState } from 'react'
import { fetchNotices, readNotices, type Notice } from '../api'
import { card, secondary } from '../ui'

/** What a release changed in your plan (ADR-0087), until you've seen it: on Home and Plan. It
 * changes nothing itself; your level stays where it is. Hidden with nothing to say. */
export default function PlanNotices() {
  const [notices, setNotices] = useState<Notice[]>([])
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchNotices(controller.signal)
      .then((found) => setNotices(found ?? []))
      .catch(() => setNotices([])) // the page below still shows
    return () => controller.abort()
  }, [])

  if (notices.length === 0) return null

  const gotIt = async () => {
    setFailed(false)
    try {
      await readNotices(notices.map((n) => n.id))
      setNotices([])
    } catch {
      setFailed(true)
    }
  }

  return (
    <section aria-labelledby="plan-notices" className={`${card} flex flex-col gap-3`}>
      <h2 id="plan-notices" className="m-0 text-xl font-bold">
        Something changed in your plan
      </h2>
      <ul className="m-0 flex flex-col gap-1 pl-5">
        {notices.map((n) => (
          <li key={n.id}>{n.text}</li>
        ))}
      </ul>
      <p className="m-0 text-[var(--slate)]">Your levels stay where they are.</p>
      <button type="button" className={`${secondary} self-start`} onClick={() => void gotIt()}>
        Got it
      </button>
      {failed && (
        <p role="status" className="status m-0">
          That didn't work. Check your connection and try again.
        </p>
      )}
    </section>
  )
}
