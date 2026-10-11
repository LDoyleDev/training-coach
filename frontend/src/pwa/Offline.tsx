import { useSyncExternalStore } from 'react'

function subscribe(listener: () => void) {
  window.addEventListener('online', listener)
  window.addEventListener('offline', listener)
  return () => {
    window.removeEventListener('online', listener)
    window.removeEventListener('offline', listener)
  }
}

/** Says so when the phone has no connection, instead of leaving a page that won't load. */
export default function OfflineNotice() {
  const online = useSyncExternalStore(subscribe, () => navigator.onLine)
  if (online) return null
  return (
    <p
      role="status"
      className="m-0 rounded-2xl border-2 border-[var(--ink)] bg-[var(--paper)] p-3 font-bold"
    >
      You're offline. Training Coach needs a connection to load and save; it will work again as soon
      as you're back online.
    </p>
  )
}
