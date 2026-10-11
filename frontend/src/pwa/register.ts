/** Where the service worker may run: built for production, and served over https (or from
 * this computer, for trying a build). Never in `npm run dev`, where it would cache dev files. */
export function canRegister(where: {
  production: boolean
  protocol: string
  hostname: string
  supported: boolean
}): boolean {
  if (!where.production || !where.supported) return false
  return (
    where.protocol === 'https:' || where.hostname === 'localhost' || where.hostname === '127.0.0.1'
  )
}

/** Registers /sw.js (D3) when `canRegister` allows. A failure only means no offline copy, so
 * it is never shown. Resolves to whether it registered. */
export async function registerServiceWorker(
  production: boolean = import.meta.env.PROD,
): Promise<boolean> {
  const allowed = canRegister({
    production,
    protocol: window.location.protocol,
    hostname: window.location.hostname,
    supported: 'serviceWorker' in navigator,
  })
  if (!allowed) return false
  try {
    await navigator.serviceWorker.register('/sw.js', { scope: '/' })
    return true
  } catch {
    return false
  }
}
