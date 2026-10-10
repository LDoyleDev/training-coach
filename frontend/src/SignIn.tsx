import { useEffect, useRef, useState } from 'react'
import { addPasskey, passkeysSupported, redeemLink, signInWithPasskey } from './api'
import { nextPage } from './next'
import { primary, primaryInline, secondary } from './ui'

type State =
  | 'choose' // no link: sign in with a passkey, or get a link from the bot
  | 'working'
  | 'signed-in'
  | 'refused'
  | 'use-passkey' // a link once a passkey exists: the fingerprint signs in (ADR-0040)
  | 'passkey-refused'
  | 'error'

type Offer = 'none' | 'offer' | 'adding' | 'added' | 'failed'

const PROBLEMS: Record<'refused' | 'passkey-refused' | 'error', string> = {
  refused:
    'This link has expired or was already used. Send /login to the bot for a new one; each link works once, for 10 minutes.',
  'passkey-refused':
    "That didn't sign you in. Try again, or send /login to the bot and add a passkey on this device.",
  error: "Couldn't reach the server. Check your connection and try again.",
}

/**
 * /signin (ADR-0036). With #<token> from the bot's /login, the link signs in (the fragment is
 * never sent to servers and is cleared from the address bar), then offers a passkey. Without
 * a token, it signs in with a passkey: the phone's fingerprint or face.
 */
export default function SignIn() {
  // Read once, on the first render, before the effect clears it from the address bar.
  const [token] = useState(() => window.location.hash.slice(1))
  const [next] = useState(() => nextPage(window.location.search))
  const [state, setState] = useState<State>(token ? 'working' : 'choose')
  const [offer, setOffer] = useState<Offer>('none')
  const [supported] = useState(passkeysSupported)
  // A link works once: never post it twice (React runs effects twice in development).
  const posted = useRef(false)

  useEffect(() => {
    window.history.replaceState(null, '', window.location.pathname)
    if (!token || posted.current) return
    posted.current = true
    redeemLink(token)
      .then((result) => {
        setState(result)
        if (result === 'signed-in' && passkeysSupported()) setOffer('offer')
      })
      .catch(() => setState('error'))
  }, [token])

  const usePasskey = () => {
    setState('working')
    signInWithPasskey()
      .then((ok) => (ok ? window.location.assign(next) : setState('passkey-refused')))
      .catch(() => setState('passkey-refused'))
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
      <main className="mt-4 flex flex-col gap-3">
        <h1>Sign in</h1>

        {state === 'working' && (
          <p className="status" role="status">
            Signing you in…
          </p>
        )}

        {(state === 'choose' || state === 'passkey-refused' || state === 'use-passkey') && (
          <>
            {state === 'use-passkey' && (
              <p className="status" role="status">
                You've set up a passkey, so a link from the bot doesn't sign you in on its own any
                more. Use your fingerprint or face here. Lost your phone or passkey? Send /recover
                to the bot.
              </p>
            )}
            {state === 'passkey-refused' && (
              <p className="status status-error" role="alert">
                {PROBLEMS['passkey-refused']}
              </p>
            )}
            {supported ? (
              <p>
                <button type="button" onClick={usePasskey} className={primary}>
                  Sign in with fingerprint or face
                </button>
              </p>
            ) : (
              <p className="status">This browser can't use passkeys.</p>
            )}
            <p>No passkey on this device yet? Send /login to the bot and open the link it sends.</p>
          </>
        )}

        {(state === 'refused' || state === 'error') && (
          <p className="status status-error" role="alert">
            {PROBLEMS[state]}
          </p>
        )}

        {state === 'signed-in' && (
          <>
            <p className="status" role="status">
              You're signed in on this device.
            </p>
            {offer === 'offer' && (
              <p>
                <button type="button" onClick={add} className={secondary}>
                  Use your fingerprint next time
                </button>
              </p>
            )}
            {offer === 'adding' && <p role="status">Follow your phone's prompt…</p>}
            {offer === 'added' && (
              <p role="status">Passkey added. Next time, sign in with your fingerprint or face.</p>
            )}
            {offer === 'failed' && (
              <p role="alert">
                The passkey wasn't added. You can try again from this page after your next /login.
              </p>
            )}
            <p>
              <a href={next} className={`${primaryInline} inline-flex items-center no-underline`}>
                Continue
              </a>
            </p>
          </>
        )}
      </main>
    </div>
  )
}
