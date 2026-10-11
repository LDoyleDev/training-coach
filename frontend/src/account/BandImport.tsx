import { useEffect, useState } from 'react'
import {
  type BandImport as Status,
  fetchBandImport,
  makeBandSecret,
  removeBandSecret,
  SignedOutError,
  StaleSignInError,
} from '../api'
import { actions, card, primaryInline, secondary } from '../ui'

function failure(error: unknown): string {
  if (error instanceof SignedOutError) return 'Your sign-in ended. Sign in again, then retry.'
  if (error instanceof StaleSignInError)
    return 'A new secret needs you to confirm it’s you. Try again and confirm with your fingerprint when your phone asks.'
  return "That didn't work. Check your connection and try again."
}

const when = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })

/**
 * Band import (ADR-0054): the secret the Health Connect Webhook app on the phone sends with
 * band data. Made here and shown once; the server keeps only its hash. Steps for the phone are
 * in docs/runbooks/band-import.md.
 */
export default function BandImport() {
  const [status, setStatus] = useState<Status | null>(null)
  const [secret, setSecret] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchBandImport(controller.signal)
      .then(setStatus)
      .catch(() => {}) // the section stays hidden; the rest of the page still works
    return () => controller.abort()
  }, [])

  if (!status) return null

  const make = async () => {
    setNote(null)
    try {
      const { secret: shown, ...made } = await makeBandSecret()
      setSecret(shown)
      setStatus(made)
    } catch (error) {
      setNote(failure(error))
    }
  }

  const remove = async () => {
    setNote(null)
    setSecret(null)
    try {
      await removeBandSecret()
      setStatus({ ...status, exists: false, created_at: null, last_used_at: null })
      setNote('Removed. The phone can’t send band data until you make a new secret.')
    } catch (error) {
      setNote(failure(error))
    }
  }

  return (
    <section aria-labelledby="band-import" className={card}>
      <h2 id="band-import" className="mb-2 text-xl">
        Band import
      </h2>
      <p>
        Your band’s workouts, sleep, steps, heart rate and weight reach the coach from the Health
        Connect Webhook app on your phone. It needs the address and a secret from here.
      </p>
      {status.url ? (
        <p className="break-all">
          Address: <code>{status.url}</code>
        </p>
      ) : (
        <p>Band import needs the server’s public address set first.</p>
      )}
      {status.exists && (
        <p>
          {status.last_used_at
            ? `Last data arrived ${when(status.last_used_at)}.`
            : 'No data has arrived yet.'}
        </p>
      )}
      {secret && (
        <div role="status" className="my-2 rounded-xl border-2 border-[var(--ink)] p-2">
          <p>
            Your new secret. Copy it into the app now: it won’t be shown again. In the app, add the
            header <code>Authorization</code> with the value <code>Bearer</code>, a space and the
            secret.
          </p>
          <p className="font-mono break-all select-all">{secret}</p>
        </div>
      )}
      <p className={actions}>
        <button type="button" className={primaryInline} onClick={() => void make()}>
          {status.exists ? 'Make a new secret' : 'Make a secret'}
        </button>
        {status.exists && (
          <button type="button" className={secondary} onClick={() => void remove()}>
            Stop band import
          </button>
        )}
      </p>
      {status.exists && !secret && (
        <p className="text-sm">A new secret replaces the old one: enter it in the app again.</p>
      )}
      {note && <p role="status">{note}</p>}
    </section>
  )
}
