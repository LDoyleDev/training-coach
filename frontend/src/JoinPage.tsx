import { useState } from 'react'
import { addPasskey, joinWithInvite, passkeysSupported } from './api'
import { primaryInline } from './ui'

type State = 'ready' | 'working' | 'joined' | 'used' | 'full' | 'off' | 'error'
type Offer = 'offer' | 'adding' | 'added' | 'failed'

const SAID: Record<Exclude<State, 'ready' | 'working' | 'joined'>, string> = {
  used: 'This invite has expired or was used. Ask for a new one.',
  full: "There's no room for another member just now.",
  off: "Invites aren't open.",
  error: "That didn't work. Check your connection and try again.",
}

/**
 * /join#<token> (ADR-0059): an invite to join. The fragment never reaches a server and is cleared
 * from the address bar. The person says they're an adult and joins, signed in; then the passkey,
 * so they can sign in again. The privacy notice comes here too, before anyone is invited
 * (multi-user-plan.md, step 11); until then invites are off.
 */
export default function JoinPage() {
  // Read once, on the first render, and cleared at once: an invite works once.
  const [token] = useState(() => {
    const found = window.location.hash.slice(1)
    window.history.replaceState(null, '', window.location.pathname)
    return found
  })
  const [adult, setAdult] = useState(false)
  const [state, setState] = useState<State>('ready')
  const [offer, setOffer] = useState<Offer>('offer')

  const join = () => {
    setState('working')
    joinWithInvite(token, adult)
      .then(setState)
      .catch(() => setState('error'))
  }
  const add = () => {
    setOffer('adding')
    addPasskey()
      .then((ok) => setOffer(ok ? 'added' : 'failed'))
      .catch(() => setOffer('failed'))
  }

  return (
    <div className="page">
      <header className="masthead">
        <span className="wordmark">Training Coach</span>
      </header>
      <main className="flex flex-col gap-3">
        <h1 className="text-3xl font-extrabold">Join Training Coach</h1>
        <p className="m-0">
          This is a private test for invited family and friends. It isn't open to anyone else, and
          you can leave and delete everything at any time on Account.
        </p>
        {!token && <p>This link has no invite in it. Open the link you were sent.</p>}
        {token && state !== 'joined' && (
          <>
            <p className="m-0">
              You were invited. You start with your own plan and find your level as you go.
            </p>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={adult}
                onChange={(e) => setAdult(e.target.checked)}
                className="h-6 w-6"
              />
              I'm 18 or over
            </label>
            <button
              type="button"
              className={`${primaryInline} self-start`}
              disabled={!adult || state === 'working'}
              onClick={join}
            >
              Join
            </button>
            {state in SAID && <p role="status">{SAID[state as keyof typeof SAID]}</p>}
          </>
        )}
        {state === 'joined' && (
          <>
            <p role="status" className="m-0">
              You're in.
            </p>
            {passkeysSupported() && offer !== 'added' && (
              <>
                <p className="m-0">
                  Add a passkey so you can sign in again with your fingerprint or face.
                </p>
                <button
                  type="button"
                  className={`${primaryInline} self-start`}
                  disabled={offer === 'adding'}
                  onClick={add}
                >
                  Add a passkey
                </button>
                {offer === 'failed' && <p>The passkey wasn't added. Try again.</p>}
              </>
            )}
            {offer === 'added' && <p className="m-0">Passkey added.</p>}
            <a href="/">Go to today</a>
          </>
        )}
      </main>
    </div>
  )
}
