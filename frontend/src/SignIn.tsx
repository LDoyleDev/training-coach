import { useEffect, useRef, useState } from 'react'
import { redeemLink } from './api'

type State = 'working' | 'signed-in' | 'refused' | 'missing' | 'error'

const MESSAGES: Record<Exclude<State, 'signed-in'>, string> = {
  working: 'Signing you in…',
  refused:
    'This link has expired or was already used. Send /login to the bot for a new one; each link works once, for 10 minutes.',
  missing: 'This sign-in link is incomplete. Send /login to the bot and open the link it sends.',
  error: "Couldn't reach the server. Check your connection and open the link again.",
}

/**
 * /signin#<token>: the one-time link from the bot's /login (ADR-0036). The token travels in
 * the fragment, which browsers never send to servers, and is removed from the address bar as
 * soon as it has been posted.
 */
export default function SignIn() {
  // Read once, on the first render, before the effect clears it from the address bar.
  const [token] = useState(() => window.location.hash.slice(1))
  const [state, setState] = useState<State>(token ? 'working' : 'missing')

  // A link works once: never post it twice (React runs effects twice in development).
  const posted = useRef(false)

  useEffect(() => {
    window.history.replaceState(null, '', window.location.pathname)
    if (!token || posted.current) return
    posted.current = true
    redeemLink(token)
      .then((ok) => setState(ok ? 'signed-in' : 'refused'))
      .catch(() => setState('error'))
  }, [token])

  return (
    <div className="page">
      <header className="masthead">
        <span className="wordmark">Training Coach</span>
      </header>
      <main>
        <h1>Sign in</h1>
        {state === 'signed-in' ? (
          <>
            <p className="status" role="status">
              You're signed in on this device.
            </p>
            <p>
              <a href="/">Continue</a>
            </p>
          </>
        ) : (
          <p
            className={state === 'working' ? 'status' : 'status status-error'}
            role={state === 'working' ? 'status' : 'alert'}
          >
            {MESSAGES[state]}
          </p>
        )}
      </main>
    </div>
  )
}
