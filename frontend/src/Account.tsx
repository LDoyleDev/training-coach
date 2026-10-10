import AppShell from './components/AppShell'
import AiComments from './account/AiComments'
import CopyForAI from './account/CopyForAI'
import Toast from './components/Toast'
import { card, danger, primaryInline, secondary } from './ui'
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

/** One item in a list, with its action at the end; wraps on a phone. */
const row =
  'flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] py-2 last:border-0'

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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1>Account</h1>
        <button type="button" onClick={leave}>
          Sign out
        </button>
      </div>
      {state.status === 'loading' && (
        <p className="status" role="status">
          Loading…
        </p>
      )}
      {state.status === 'error' && (
        <div className={card}>
          <p className="status-error m-0 mb-3" role="alert">
            Couldn't load your sign-ins. Check your connection.
          </p>
          <button type="button" onClick={load}>
            Try again
          </button>
        </div>
      )}
      {state.status === 'signed-out' && (
        <div className={card}>
          <p className="m-0 mb-3">You're not signed in.</p>
          <a
            href="/signin?next=/account"
            className={`${primaryInline} inline-flex items-center no-underline`}
          >
            Sign in
          </a>
        </div>
      )}
      {state.status === 'ready' && (
        <>
          <Toast text={note} onClose={() => setNote(null)} />

          <section aria-labelledby="passkeys" className={card}>
            <h2 id="passkeys" className="mb-2 text-xl">
              Passkeys
            </h2>
            {state.signIns.passkeys.length === 0 ? (
              <p>No passkeys yet: you sign in with a link from the bot.</p>
            ) : (
              <ul className="m-0 mb-3 list-none p-0">
                {state.signIns.passkeys.map((key) => (
                  <li key={key.id} className={row}>
                    <span>
                      {key.name} · added {day(key.created_at)}
                      {key.last_used_at ? ` · last used ${day(key.last_used_at)}` : ''}
                    </span>
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

          <section aria-labelledby="devices" className={card}>
            <h2 id="devices" className="mb-2 text-xl">
              Signed-in browsers
            </h2>
            <ul className="m-0 list-none p-0">
              {state.signIns.devices.map((device) => (
                <li key={device.id} className={row}>
                  <span>
                    {device.current ? 'This browser' : device.label} · last seen{' '}
                    {day(device.last_seen_at)}
                  </span>
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

          <section aria-labelledby="readiness" className={card}>
            <h2 id="readiness" className="mb-2 text-xl">
              Readiness
            </h2>
            <p className="mt-0">Seven questions about your health before hard exercise.</p>
            <a href="/readiness" className={`${secondary} inline-flex items-center no-underline`}>
              Answer or update them
            </a>
          </section>

          <section aria-labelledby="your-data" className={card}>
            <h2 id="your-data" className="mb-2 text-xl">
              Your data
            </h2>
            <p className="mt-0">
              Everything stored about you: workouts, tests, measurements, habits, settings and your
              photos, as one zip file.
            </p>
            <button type="button" onClick={download}>
              Download all my data
            </button>
          </section>

          <CopyForAI />
          <AiComments />

          <section aria-labelledby="erase" className={card}>
            <h2 id="erase" className="mb-2 text-xl">
              Erase all my data
            </h2>
            <p className="mt-0">
              Deletes everything stored about you: workouts, tests, measurements, habits, settings,
              photos, passkeys and every signed-in browser. You start again from the first session.
              It can't be undone; download your data first if you want a copy. Backups that still
              hold it are deleted within 5 weeks.
            </p>
            <form onSubmit={erase} className="flex flex-col gap-3">
              <label className="flex flex-col gap-1">
                <span>
                  Type <strong>erase</strong> to confirm
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
                <button type="submit" disabled={confirm !== 'erase'} className={danger}>
                  Erase all my data
                </button>
              </div>
            </form>
          </section>
        </>
      )}
    </AppShell>
  )
}
