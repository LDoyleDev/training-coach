import { useSyncExternalStore } from 'react'
import { type ConsentCategory, type Consents, fetchConsents } from '../api'

// Read once per page and shared: every gated part of a page asks the same question, and a yes
// or a withdrawal on one part shows on the others at once.
let known: Consents | null | undefined // undefined: not read yet; null: couldn't be read
let reading = false
const listeners = new Set<() => void>()

/** The view a give or a withdrawal answered with. */
export function remember(view: Consents | null) {
  known = view
  listeners.forEach((listener) => listener())
}

/** For tests: the next hook reads again. */
export function forgetConsents() {
  known = undefined
  reading = false
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  if (known === undefined && !reading) {
    reading = true
    fetchConsents()
      // Only a real answer counts: an older server or anything else reads as unknown.
      .then((found) => remember(Array.isArray(found?.categories) ? found : null))
      .catch(() => remember(null))
      .finally(() => (reading = false))
  }
  return () => listeners.delete(listener)
}

/** What you've said yes to (ADR-0090): undefined while reading, null when it couldn't be read
 *  (signed out or offline: the page then says so itself). */
export function useConsents(): Consents | null | undefined {
  return useSyncExternalStore(subscribe, () => known)
}

/** Whether a category is open to you. Unknown counts as open: the server still refuses, and the
 *  page shows its own error. The owner's are always open. */
export default function useConsent(category: ConsentCategory): 'loading' | 'open' | 'closed' {
  const view = useConsents()
  if (view === undefined) return 'loading'
  const found = view?.categories.find((c) => c.category === category)
  return found?.open === false ? 'closed' : 'open'
}
