import { useCallback, useEffect, useState } from 'react'
import { type Connection, fetchConnections, revokeConnection } from '../api/connect'
import { card } from '../ui'

const LABELS: Record<string, string> = {
  'training:read': 'training',
  'body:read': 'body measurements',
  'readiness:read': 'readiness and daily checks',
}

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

type State =
  | { status: 'loading' }
  | { status: 'hidden' }
  | { status: 'error' }
  | { status: 'ready'; apps: Connection[] }

/**
 * Connected AI apps (ADR-0047 C): each app that may read your data, what it may read and when
 * it last did, with Revoke. Connecting starts in the AI app itself, so there's no Add here.
 */
export default function AiApps() {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [note, setNote] = useState<string | null>(null)

  const load = useCallback(() => {
    fetchConnections()
      .then((apps) => setState(apps ? { status: 'ready', apps } : { status: 'hidden' }))
      .catch(() => setState({ status: 'error' }))
  }, [])

  useEffect(load, [load])

  const revoke = (app: Connection) => {
    revokeConnection(app.id)
      .then(() => setNote(`“${app.client_name}” can't read anything now.`))
      .catch(() => setNote("That didn't work. Check your connection and try again."))
      .finally(load)
  }

  if (state.status === 'hidden') return null
  return (
    <section aria-labelledby="ai-apps" className={card}>
      <h2 id="ai-apps" className="mb-2 text-xl">
        Connected AI apps
      </h2>
      {state.status === 'loading' && <p className="m-0">Loading…</p>}
      {state.status === 'error' && (
        <p className="status-error m-0" role="alert">
          Couldn't load your connected apps.
        </p>
      )}
      {state.status === 'ready' && state.apps.length === 0 && (
        <p className="m-0">
          None. To connect one, add this site's /mcp address as a connector in your AI app; you
          approve it here with your fingerprint.
        </p>
      )}
      {state.status === 'ready' && state.apps.length > 0 && (
        <ul className="m-0 list-none p-0">
          {state.apps.map((app) => (
            <li
              key={app.id}
              className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] py-2 last:border-0"
            >
              <span className="min-w-0 break-words">
                Calls itself “{app.client_name}” · {app.redirect_host} · reads{' '}
                {app.scopes.map((s) => LABELS[s] ?? s).join(', ')} · connected {day(app.created_at)}
                {app.last_used_at ? ` · last used ${day(app.last_used_at)}` : ' · not used yet'}
                {` · ends ${day(app.ends_at)}`}
              </span>
              <button
                type="button"
                onClick={() => revoke(app)}
                aria-label={`Revoke ${app.client_name}`}
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      )}
      {note && (
        <p className="m-0 mt-2" role="status">
          {note}
        </p>
      )}
    </section>
  )
}
