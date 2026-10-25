import { useEffect } from 'react'

/** Keep the screen on while `active`, asking again when the page is visible again (a lock ends
 * when the page is hidden). Released when `active` ends or the page goes; does nothing where
 * the browser has no wake lock. */
export default function useWakeLock(active: boolean): void {
  useEffect(() => {
    if (!active) return
    let live = true
    let lock: WakeLockSentinel | null = null
    const acquire = () => {
      try {
        navigator.wakeLock
          ?.request('screen')
          .then((next) => {
            if (!live) return void next.release().catch(() => {})
            lock?.release().catch(() => {})
            lock = next
          })
          .catch(() => {})
      } catch {
        // no wake lock here: the session still runs
      }
    }
    const onVisible = () => {
      if (document.visibilityState === 'visible') acquire()
    }
    acquire()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      live = false
      document.removeEventListener('visibilitychange', onVisible)
      lock?.release().catch(() => {})
    }
  }, [active])
}
