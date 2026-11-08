import { type ReactNode, useState } from 'react'
import { type ConsentCategory, giveConsent, SignedOutError, StaleWordingError } from '../api'
import { actions, card, primaryInline, secondary } from '../ui'
import useConsent, { remember } from './useConsent'
import { DRAFT, VERSIONS, WORDING } from './wording'

function failure(error: unknown): string {
  if (error instanceof SignedOutError) return 'Your sign-in ended. Sign in again, then retry.'
  if (error instanceof StaleWordingError)
    return 'This wording changed since the page opened. Reload the page to read the new one.'
  return "That didn't work. Check your connection and try again."
}

/**
 * The consent card (ADR-0090): what a category keeps and why, with "Yes, keep it" and
 * "Not now". ``onNotNow`` replaces the short "stays off" line, for the daily check's gate.
 */
export function ConsentCard({
  category,
  onGiven,
  onNotNow,
}: {
  category: ConsentCategory
  onGiven?: () => void
  onNotNow?: () => void
}) {
  const [later, setLater] = useState(false)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const words = WORDING[category]

  if (later)
    return (
      <p className="status m-0">
        {words.off}{' '}
        <button type="button" onClick={() => setLater(false)}>
          Turn it on
        </button>
      </p>
    )

  const yes = async () => {
    setBusy(true)
    setNote(null)
    try {
      remember(await giveConsent(category, VERSIONS[category]))
      onGiven?.()
    } catch (error) {
      setNote(failure(error))
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby={`consent-${category}`} className={`${card} flex flex-col gap-3`}>
      <h2 id={`consent-${category}`} className="m-0 text-xl">
        {words.title}
      </h2>
      <p className="m-0">{words.text}</p>
      <p className="m-0 text-sm text-[var(--slate)]">{DRAFT}</p>
      <div className={actions}>
        <button type="button" className={primaryInline} disabled={busy} onClick={() => void yes()}>
          Yes, keep it
        </button>
        <button type="button" className={secondary} onClick={onNotNow ?? (() => setLater(true))}>
          Not now
        </button>
      </div>
      {note && (
        <p role="alert" className="status-error m-0">
          {note}
        </p>
      )}
    </section>
  )
}

/**
 * A health page's content, once its category is open to you; the consent card until then.
 * ``quiet`` shows nothing instead, for the small extras on other pages (a summary, a chart).
 * The owner's categories are always open, so they never see the card.
 */
export default function Consented({
  category,
  quiet = false,
  children,
}: {
  category: ConsentCategory
  quiet?: boolean
  children: ReactNode
}) {
  const consent = useConsent(category)
  if (consent === 'open') return children
  if (consent === 'loading' || quiet) return null
  return <ConsentCard category={category} />
}
