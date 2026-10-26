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

/** The start of the coach's own reader's version string (ADR-0070); HC Webhook's is bare. */
const READER = 'tc-reader/'

/** Whether the phone sends with HC Webhook: before any sync, the reader that replaced it. */
const fromWebhook = (version: string | null) => version !== null && !version.startsWith(READER)

/** The app that sent the last stored sync, named from its version string. */
const sender = (version: string) =>
  fromWebhook(version)
    ? `HC Webhook ${version}`
    : `the Coach reader ${version.slice(READER.length)}`

/** Why the last sync with the right secret stored nothing, and what to do about it. */
function refused(reason: NonNullable<Status['refused_reason']>, webhook: boolean): string {
  switch (reason) {
    case 'too_large':
      return webhook
        ? 'it was over 5 MB. In HC Webhook, set heart rate to 1 minute, not Full.'
        : 'it was over 5 MB. The reader tries it again, and after three refusals skips it and says so on its screen.'
    case 'not_json':
      return webhook
        ? 'it wasn’t JSON. In HC Webhook, set the delivery format to JSON.'
        : 'it wasn’t JSON. Update the Coach reader.'
    case 'failed':
      return 'the coach couldn’t store it. The app sends it again at its next sync.'
    case 'skipped':
      return 'nothing in it made sense, so all of it was left out. Check the phone’s clock.'
  }
}

const when = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })

/**
 * Band import (ADR-0055, ADR-0070): the secret the Coach reader on the phone (or, before it,
 * HC Webhook) sends with band data. Made here and shown once; the server keeps only its hash. Steps for the phone are
 * in docs/runbooks/band-import.md. "Last data arrived" is the last sync that brought a record,
 * not just the last call: the two drift apart when the band stops syncing to the phone. A sync
 * with the right secret that stored nothing is shown with why, while it is the newest.
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
  const webhook = fromWebhook(status.app_version)

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
      setStatus({
        ...status,
        exists: false,
        created_at: null,
        last_used_at: null,
        last_taken_at: null,
        refused_at: null,
        refused_reason: null,
        app_version: null,
      })
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
        {webhook
          ? 'Your band’s workouts, sleep, steps, heart rate and weight reach the coach from the Health Connect Webhook app on your phone. It needs the address and a secret from here.'
          : 'Your band’s workouts, sleep, steps and heart rate reach the coach from the Coach reader app on your phone. It needs a secret from here.'}
      </p>
      {/* The reader has the address built in, so only HC Webhook is shown it (review of #376). */}
      {webhook &&
        (status.url ? (
          <p className="break-all">
            Address: <code>{status.url}</code>
          </p>
        ) : (
          <p>Band import needs the server’s public address set first.</p>
        ))}
      {status.exists && (
        <p>
          {status.last_taken_at
            ? `Last data arrived ${when(status.last_taken_at)}.`
            : 'No data has arrived yet.'}
          {status.last_used_at &&
            status.last_used_at !== status.last_taken_at &&
            ` Last sync ${when(status.last_used_at)}.`}
          {status.app_version && ` From ${sender(status.app_version)}.`}
        </p>
      )}
      {status.exists && status.refused_at && status.refused_reason && (
        <p>
          Last refused sync {when(status.refused_at)}: {refused(status.refused_reason, webhook)}
        </p>
      )}
      {secret && (
        <div role="status" className="my-2 rounded-xl border-2 border-[var(--ink)] p-2">
          <p>
            Your new secret. Copy it into the app now: it won’t be shown again.{' '}
            {webhook ? (
              <>
                In the app, add the header <code>Authorization</code> with the value{' '}
                <code>Bearer</code>, a space and the secret.
              </>
            ) : (
              'In the Coach reader, paste it under Secret and tap Save the secret.'
            )}
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
