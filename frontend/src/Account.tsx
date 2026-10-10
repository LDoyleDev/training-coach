import AppShell from './components/AppShell'
import AiComments from './account/AiComments'
import CopyForAI from './account/CopyForAI'
import { type FormEvent, useCallback, useEffect, useState } from 'react'
import {
  addPasskey,
  downloadExport,
  eraseAllMyData,
  fetchSignIns,
  passkeysSupported,
  removePasskey,
  signOut,
  signOutDevice,
  StaleSignInError,
  type SignIns,
} from './api'

const STALE =
  'For safety, changing passkeys needs a recent sign-in. Sign out, sign back in with your ' +
  'fingerprint (or /recover if you lost it), then do it within 10 minutes.'

type State =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; signIns: SignIns }

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

/**
 * /account (ADR-0036): your passkeys and signed-in browsers. Remove a passkey or sign a lost
 * phone out; add a passkey on this device; sign out here. Download or erase all your data.
 */
export default function Account() {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [note, setNote] = useState<string | null>(null)
  const [confirm, setConfirm] = useState('')

  const load = useCallback(() => {
    fetchSignIns()
      .then((signIns) =>
        setState(signIns ? { status: 'ready', signIns } : { status: 'signed-out' }),
      )
      .catch(() => setState({ status: 'error' }))
  }, [])

  useEffect(load, [load])

  const act = (work: Promise<unknown>, done: string) => {
    work
      .then(() => setNote(done))
      .catch((error: unknown) =>
        setNote(
          error instanceof StaleSignInError
            ? STALE
            : "That didn't work. Check your connection and try again.",
        ),
      )
      .finally(load)
  }

  const add = () => {
    addPasskey()
      .then((ok) => setNote(ok ? 'Passkey added.' : "The passkey wasn't added."))
      .catch((error: unknown) =>
        setNote(error instanceof StaleSignInError ? STALE : "The passkey wasn't added."),
      )
      .finally(load)
  }

  const download = () => {
    setNote('Preparing your data…')
    downloadExport()
      .then((zip) => {
        const url = URL.createObjectURL(zip)
        const link = document.createElement('a')
        link.href = url
        link.download = `training-coach-${new Date().toISOString().slice(0, 10)}.zip`
        link.click()
        URL.revokeObjectURL(url)
        setNote('Your data is downloading.')
      })
      .catch((error: unknown) =>
        setNote(
          error instanceof StaleSignInError
            ? STALE.replace('changing passkeys', 'downloading everything')
            : "That didn't work. Check your connection and try again.",
        ),
      )
  }

  const erase = (event: FormEvent) => {
    event.preventDefault()
    eraseAllMyData(confirm)
      .then(() => window.location.assign('/signin'))
      .catch((error: unknown) =>
        setNote(
          error instanceof StaleSignInError
            ? STALE.replace('changing passkeys', 'erasing everything')
            : "That didn't work. Nothing was erased; check your connection and try again.",
        ),
      )
  }

  const leave = () => {
    signOut().finally(() => window.location.assign('/signin'))
  }

  return (
    <AppShell>
      <h1>Sign-in and devices</h1>
      {state.status === 'loading' && (
        <p className="status" role="status">
          Loading…
        </p>
      )}
      {state.status === 'error' && (
        <p className="status status-error" role="alert">
          Couldn't load your sign-ins. Check your connection and reload the page.
        </p>
      )}
      {state.status === 'signed-out' && (
        <p className="status">
          You're not signed in. <a href="/signin">Sign in</a>
        </p>
      )}
      {state.status === 'ready' && (
        <>
          {note && <p role="status">{note}</p>}

          <section aria-labelledby="passkeys">
            <h2 id="passkeys">Passkeys</h2>
            {state.signIns.passkeys.length === 0 ? (
              <p>No passkeys yet: you sign in with a link from the bot.</p>
            ) : (
              <ul>
                {state.signIns.passkeys.map((key) => (
                  <li key={key.id}>
                    {key.name} · added {day(key.created_at)}
                    {key.last_used_at ? ` · last used ${day(key.last_used_at)}` : ''}{' '}
                    <button
                      type="button"
                      onClick={() => act(removePasskey(key.id), 'Passkey removed.')}
                      aria-label={`Remove passkey ${key.name}`}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {passkeysSupported() && (
              <button type="button" onClick={add}>
                Add a passkey on this device
              </button>
            )}
          </section>

          <section aria-labelledby="devices">
            <h2 id="devices">Signed-in browsers</h2>
            <ul>
              {state.signIns.devices.map((device) => (
                <li key={device.id}>
                  {device.current ? 'This browser' : device.label} · last seen{' '}
                  {day(device.last_seen_at)}{' '}
                  {device.current ? (
                    <button type="button" onClick={leave}>
                      Sign out
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => act(signOutDevice(device.id), 'That browser is signed out.')}
                      aria-label={`Sign out ${device.label}`}
                    >
                      Sign out
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="readiness">
            <h2 id="readiness">Readiness</h2>
            <p>
              Seven questions about your health before hard exercise.{' '}
              <a href="/readiness">Answer or update them</a>
            </p>
          </section>

          <section aria-labelledby="your-data">
            <h2 id="your-data">Your data</h2>
            <p>
              Everything stored about you: workouts, tests, measurements, habits, settings and your
              photos, as one zip file.
            </p>
            <p>
              <button type="button" onClick={download}>
                Download all my data
              </button>
            </p>
          </section>

          <CopyForAI />
          <AiComments />

          <section aria-labelledby="erase">
            <h2 id="erase">Erase all my data</h2>
            <p>
              Deletes everything stored about you: workouts, tests, measurements, habits, settings,
              photos, passkeys and every signed-in browser. You start again from the first session.
              It can't be undone; download your data first if you want a copy. Backups that still
              hold it are deleted within 5 weeks.
            </p>
            <form onSubmit={erase}>
              <label>
                Type <strong>erase</strong> to confirm{' '}
                <input
                  value={confirm}
                  onChange={(event) => setConfirm(event.target.value)}
                  autoComplete="off"
                  autoCapitalize="none"
                  spellCheck={false}
                />
              </label>{' '}
              <button type="submit" disabled={confirm !== 'erase'}>
                Erase all my data
              </button>
            </form>
          </section>
        </>
      )}
    </AppShell>
  )
}
