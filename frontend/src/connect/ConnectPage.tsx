import { useEffect, useState } from 'react'
import { approveConsent, type ConsentView, denyConsent, fetchConsent } from '../api/connect'
import { card, primary, secondary } from '../ui'

type State =
  | { status: 'loading' }
  | { status: 'gone' }
  | { status: 'error' }
  | { status: 'ready'; consent: ConsentView }
  | { status: 'working'; consent: ConsentView }
  | { status: 'leaving'; host: string }

const PROBLEMS: Record<string, string> = {
  passkey:
    'That didn’t confirm it’s you. Try again with your fingerprint or face. No passkey yet? ' +
    'Add one on the Account page first: a link from the bot can’t connect an AI app.',
  expired: 'This request has expired. Start again from your AI app; nothing was shared.',
}

/**
 * /connect#<handle> (ADR-0047 C): an AI app asks to read your data. Shows who it says it is,
 * where it sends you back, and what it may read (health data unticked), and asks for your
 * passkey before anything is shared. The handle is in the fragment, never sent to a server
 * except in the requests below, and cleared from the address bar.
 */
export default function ConnectPage() {
  const [handle] = useState(() => window.location.hash.slice(1))
  const [state, setState] = useState<State>({ status: handle ? 'loading' : 'gone' })
  const [ticked, setTicked] = useState<string[]>([])
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    window.history.replaceState(null, '', window.location.pathname)
    if (!handle) return
    fetchConsent(handle)
      .then((consent) => {
        if (!consent) return setState({ status: 'gone' })
        setTicked(consent.scopes.filter((s) => !s.health).map((s) => s.scope))
        setState({ status: 'ready', consent })
      })
      .catch(() => setState({ status: 'error' }))
  }, [handle])

  const leave = (url: string, host: string) => {
    setState({ status: 'leaving', host })
    window.location.assign(url)
  }

  const allow = (consent: ConsentView) => {
    setProblem(null)
    setState({ status: 'working', consent })
    approveConsent(consent, handle, ticked)
      .then((result) => {
        if ('redirect' in result) return leave(result.redirect, consent.redirect_host)
        setProblem(PROBLEMS[result.problem] ?? result.problem)
        setState({ status: 'ready', consent })
      })
      .catch(() => {
        setProblem(PROBLEMS.passkey)
        setState({ status: 'ready', consent })
      })
  }

  const refuse = (consent: ConsentView) => {
    denyConsent(handle)
      .then((url) => (url ? leave(url, consent.redirect_host) : setState({ status: 'gone' })))
      .catch(() => setState({ status: 'error' }))
  }

  const toggle = (scope: string) =>
    setTicked((now) => (now.includes(scope) ? now.filter((s) => s !== scope) : [...now, scope]))

  return (
    <div className="page">
      <header className="masthead">
        <span className="wordmark">Training Coach</span>
      </header>
      <main className="mt-4 flex flex-col gap-3">
        <h1>Connect an AI app</h1>
        {state.status === 'loading' && (
          <p className="status" role="status">
            Loading…
          </p>
        )}
        {state.status === 'gone' && (
          <p className="status status-error" role="alert">
            {PROBLEMS.expired}
          </p>
        )}
        {state.status === 'error' && (
          <p className="status status-error" role="alert">
            Couldn't reach the server. Check your connection and try again.
          </p>
        )}
        {state.status === 'leaving' && (
          <p className="status" role="status">
            Going back to {state.host}…
          </p>
        )}
        {(state.status === 'ready' || state.status === 'working') && (
          <>
            <p className="m-0">
              An app that calls itself <strong>“{state.consent.client_name}”</strong> wants to read
              your training. Anyone can give an app that name, so only go on if you just asked for
              this. When you're done, you go back to <strong>{state.consent.redirect_host}</strong>.
            </p>
            <fieldset className={card}>
              <legend className="font-bold">What it may read</legend>
              {state.consent.scopes.map((s) => (
                <label key={s.scope} className="flex min-h-11 items-center gap-3">
                  <input
                    type="checkbox"
                    className="h-5 w-5 shrink-0"
                    checked={ticked.includes(s.scope)}
                    onChange={() => toggle(s.scope)}
                  />
                  <span>{s.label}</span>
                </label>
              ))}
            </fieldset>
            <p className="m-0 text-sm">
              What it reads goes to that app's company, under your account there. It can't change
              anything here. If your AI also has other tools, such as web search, it could pass on
              what it reads. The connection ends after 90 days, or when you revoke it on the Account
              page.
            </p>
            {problem && (
              <p className="status status-error" role="alert">
                {problem}
              </p>
            )}
            <button
              type="button"
              className={primary}
              disabled={state.status === 'working' || ticked.length === 0}
              onClick={() => allow(state.consent)}
            >
              {state.status === 'working' ? 'Confirming…' : 'Allow with your fingerprint'}
            </button>
            <button
              type="button"
              className={secondary}
              disabled={state.status === 'working'}
              onClick={() => refuse(state.consent)}
            >
              Don't allow
            </button>
          </>
        )}
      </main>
    </div>
  )
}
