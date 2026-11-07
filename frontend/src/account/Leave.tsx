import { type FormEvent, useEffect, useState } from 'react'
import { fetchMe, leaveTrainingCoach, SignedOutError, StaleSignInError } from '../api'
import { card, danger } from '../ui'

/**
 * Leave Training Coach (ADR-0088), for a member only: everything of theirs is deleted, the
 * account too, with no fresh start. The owner erases instead, so it is hidden for them.
 */
export default function Leave() {
  const [member, setMember] = useState(false)
  const [confirm, setConfirm] = useState('')
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false) // one destructive request at a time

  useEffect(() => {
    const controller = new AbortController()
    fetchMe(controller.signal)
      .then((me) => setMember(me?.role === 'member'))
      .catch(() => {}) // stays hidden; the rest of the page still works
    return () => controller.abort()
  }, [])

  if (!member) return null

  const leave = (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    setNote(null)
    setBusy(true)
    leaveTrainingCoach(confirm)
      .then(() => window.location.assign('/signin'))
      .catch((error: unknown) => {
        setBusy(false)
        setNote(
          error instanceof SignedOutError
            ? 'Your sign-in ended. Sign in again, then retry.'
            : error instanceof StaleSignInError
              ? 'For safety, leaving needs you to confirm it’s you. Try again and confirm with ' +
                'your fingerprint when your phone asks.'
              : "That didn't work. Nothing was deleted; check your connection and try again.",
        )
      })
  }

  return (
    <section aria-labelledby="leave" className={card}>
      <h2 id="leave" className="mb-2 text-xl">
        Leave Training Coach
      </h2>
      <p className="mt-0">
        Deletes your account and everything stored about you, at once. You can&apos;t sign in again
        afterwards. Download your data first if you want a copy. Backups that still hold it are
        deleted within 5 weeks.
      </p>
      <form onSubmit={leave} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span>
            Type <strong>leave</strong> to confirm
          </span>
          <input
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
          />
        </label>
        <div>
          <button type="submit" disabled={confirm !== 'leave' || busy} className={danger}>
            Leave Training Coach
          </button>
        </div>
      </form>
      {note && (
        <p role="alert" className="status-error mb-0">
          {note}
        </p>
      )}
    </section>
  )
}
