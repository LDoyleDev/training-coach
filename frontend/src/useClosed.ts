import { useEffect, useState } from 'react'
import { fetchMe, type Me } from './api'

/** Who is signed in, if the app is closed to them; null otherwise (and while asking). */
export default function useClosed(): Me | null {
  const [closed, setClosed] = useState<Me | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetchMe(controller.signal)
      .then((me) => setClosed(me?.closed ? me : null))
      .catch(() => {}) // signed out or offline: the page itself says so
    return () => controller.abort()
  }, [])
  return closed
}
