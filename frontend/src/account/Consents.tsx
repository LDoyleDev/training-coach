import { useState } from 'react'
import {
  type CategoryConsent,
  type ConsentCategory,
  SignedOutError,
  StaleSignInError,
  withdrawConsent,
} from '../api'
import { remember, useConsents } from '../consent/useConsent'
import { WORDING } from '../consent/wording'
import { actions, card, danger, secondary, small } from '../ui'

const row = 'border-b border-[var(--line)] py-2 last:border-0'

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

function state(found: CategoryConsent): string {
  if (found.open) return found.at ? `On since ${day(found.at)}` : 'On'
  if (found.answer === 'given') return 'Off: the wording changed, so you’ll be asked again'
  if (found.answer === 'withdrawn' && found.at) return `Off since ${day(found.at)}`
  return 'Off: not asked yet'
}

function failure(error: unknown): string {
  if (error instanceof SignedOutError) return 'Your sign-in ended. Sign in again, then retry.'
  if (error instanceof StaleSignInError)
    return (
      'For safety, withdrawing needs you to confirm it’s you. Try again and confirm with your ' +
      'fingerprint when your phone asks.'
    )
  return "That didn't work. Nothing was deleted; check your connection and try again."
}

/**
 * What you've agreed to (ADR-0090), for a member only: each category on or off, with its date.
 * Withdrawing is as easy as saying yes, after a confirm that says what it deletes; it needs a
 * recent sign-in. The owner isn't asked, so it is hidden for them.
 */
export default function Consents() {
  const view = useConsents()
  const [asking, setAsking] = useState<ConsentCategory | null>(null)
  const [busy, setBusy] = useState(false) // one withdrawal at a time
  const [note, setNote] = useState<string | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  if (!view?.asked) return null

  const withdraw = (category: ConsentCategory) => {
    setBusy(true)
    setNote(null)
    setProblem(null)
    withdrawConsent(category)
      .then((next) => {
        remember(next)
        setAsking(null)
        setNote(`${WORDING[category].name}: withdrawn and deleted.`)
      })
      .catch((error: unknown) => setProblem(failure(error)))
      .finally(() => setBusy(false))
  }

  return (
    <section aria-labelledby="consents" className={card}>
      <h2 id="consents" className="mb-2 text-xl">
        What you&apos;ve agreed to
      </h2>
      <p className="mt-0">
        Health data is kept only for what you&apos;ve said yes to. Withdrawing deletes it at once;
        backups that still hold it are deleted within 5 weeks.
      </p>
      <ul className="m-0 list-none p-0">
        {view.categories.map((found) => {
          const words = WORDING[found.category]
          return (
            <li key={found.category} className={row}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <strong>{words.name}</strong> · {state(found)}
                </span>
                {found.answer === 'given' && asking !== found.category && (
                  <button
                    type="button"
                    className={small}
                    onClick={() => {
                      setNote(null)
                      setProblem(null)
                      setAsking(found.category)
                    }}
                    aria-label={`Withdraw ${words.name}`}
                  >
                    Withdraw
                  </button>
                )}
              </div>
              {asking === found.category && (
                <div className="mt-2 flex flex-col gap-2">
                  <p className="m-0">
                    Withdrawing deletes {words.deletes}, at once. It can&apos;t be undone.
                  </p>
                  <div className={actions}>
                    <button
                      type="button"
                      className={danger}
                      disabled={busy}
                      onClick={() => withdraw(found.category)}
                    >
                      Withdraw and delete
                    </button>
                    <button type="button" className={secondary} onClick={() => setAsking(null)}>
                      Keep it
                    </button>
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
      {note && (
        <p role="status" className="mb-0">
          {note}
        </p>
      )}
      {problem && (
        <p role="alert" className="status-error mb-0">
          {problem}
        </p>
      )}
    </section>
  )
}
