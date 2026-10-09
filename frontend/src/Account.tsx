import { useCallback, useEffect, useState } from 'react'
import {
  addPasskey,
  fetchSignIns,
  passkeysSupported,
  removePasskey,
  signOut,
  signOutDevice,
  type SignIns,
} from './api'

type State =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; signIns: SignIns }

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

/**
 * /account (ADR-0036): your passkeys and signed-in browsers. Remove a passkey or sign a lost
 * phone out; add a passkey on this device; sign out here.
 */
export default function Account() {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [note, setNote] = useState<string | null>(null)

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
      .catch(() => setNote("That didn't work. Check your connection and try again."))
      .finally(load)
  }

  const add = () => {
    addPasskey()
      .then((ok) => setNote(ok ? 'Passkey added.' : "The passkey wasn't added."))
      .catch(() => setNote("The passkey wasn't added."))
      .finally(load)
  }

  const leave = () => {
    signOut().finally(() => window.location.assign('/signin'))
  }

  return (
    <div className="page">
      <header className="masthead">
        <span className="wordmark">Training Coach</span>
      </header>
      <main>
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
          </>
        )}
      </main>
    </div>
  )
}
